"""CSV import (Google Ads / Meta Ads Manager / LinkedIn / Amazon / generic) with dry-run preview."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_workspace
from app.csv_import import FORMATS, ParsedCSV, parse_csv
from app.db import get_db
from app.deps import get_cache
from app.ingest import IngestError, ingest
from app.models import Channel, Import, Workspace
from app.schemas import ImportOut, ImportResult

router = APIRouter(prefix="/imports", tags=["imports"])

MAX_UPLOAD = 25 * 1024 * 1024
PREVIEW_ROWS = 10


def _result(parsed: ParsedCSV, *, status: str, import_id: int | None, summary: dict | None) -> dict:
    return {
        "import_id": import_id,
        "status": status,
        "detected_format": parsed.detected_format,
        "confidence": parsed.confidence,
        "channel": parsed.channel,
        "currency": parsed.currency,
        "delimiter": parsed.delimiter,
        "mapping": parsed.mapping,
        "source_columns": parsed.source_columns,
        "unmapped_columns": parsed.unmapped_columns,
        "row_count": len(parsed.rows),
        "skipped_rows": parsed.skipped_rows,
        "preview": parsed.rows[:PREVIEW_ROWS],
        "warnings": parsed.warnings,
        "summary": summary,
    }


def commit_parsed(db: Session, ws_id: int, parsed: ParsedCSV, *, source: str, filename: str | None) -> dict:
    """Shared by CSV upload and the sample-dataset import. Caller commits."""
    rows = [dict(r) for r in parsed.rows]
    res = ingest(
        db,
        ws_id,
        rows,
        source=source,
        filename=filename,
        aggregate=True,
        warnings=parsed.warnings,
        detail={"detected_format": parsed.detected_format, "mapping": parsed.mapping, "currency": parsed.currency},
    )
    summary = {
        "rows_upserted": res.upserted,
        "campaigns_created": res.campaigns_created,
        "campaigns_touched": res.campaigns_touched,
        "first_day": res.first_day,
        "last_day": res.last_day,
    }
    return _result(parsed, status="completed", import_id=res.import_id, summary=summary)


@router.post("/csv", response_model=ImportResult)
async def import_csv(
    file: UploadFile = File(...),
    dry_run: bool = Form(default=False),
    format: str | None = Form(default=None),  # noqa: A002 - matches the contract
    channel: Channel | None = Form(default=None),
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
    cache=Depends(get_cache),
):
    raw = await file.read(MAX_UPLOAD + 1)
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(status_code=413, detail="file larger than 25 MB")
    if format and format not in FORMATS:
        raise HTTPException(status_code=422, detail=f"format must be one of {sorted(FORMATS)}")
    try:
        parsed = parse_csv(raw, format_override=format, channel_override=channel)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"could not parse CSV: {exc}") from exc

    if dry_run:
        return _result(parsed, status="dry_run", import_id=None, summary=None)

    try:
        result = commit_parsed(db, ws.id, parsed, source=parsed.detected_format, filename=file.filename)
    except IngestError as exc:  # pragma: no cover - CSV rows never carry campaign ids
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    cache.invalidate_workspace(ws.id)
    return result


def _import_out(i: Import) -> dict:
    return {
        "id": i.id,
        "source": i.source,
        "filename": i.filename,
        "status": i.status,
        "rows_received": i.rows_received,
        "rows_upserted": i.rows_upserted,
        "campaigns_created": i.campaigns_created,
        "warnings": json.loads(i.warnings_json or "[]"),
        "detail": json.loads(i.detail_json or "{}"),
        "created_at": i.created_at,
    }


@router.get("", response_model=list[ImportOut])
def list_imports(
    limit: int = Query(default=50, le=500),
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(Import).where(Import.workspace_id == ws.id).order_by(Import.id.desc()).limit(limit)
    ).all()
    return [_import_out(i) for i in rows]


@router.get("/{import_id}", response_model=ImportOut)
def get_import(import_id: int, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    i = db.get(Import, import_id)
    if not i or i.workspace_id != ws.id:
        raise HTTPException(status_code=404, detail="import not found")
    return _import_out(i)
