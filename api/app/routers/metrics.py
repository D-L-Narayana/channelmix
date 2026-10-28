"""Idempotent bulk metric ingestion.

* ``POST /metrics/bulk`` upserts rows on the natural key (campaign_id, day) with a single
  ``INSERT ... ON CONFLICT DO UPDATE`` per chunk. Rows may reference campaigns by id or by
  ``channel`` + ``external_id`` (auto-created).
* An ``Idempotency-Key`` header (scoped per workspace) makes retries safe: the first completed request
  stores its response; a retry with the same key + same body replays it (``idempotent_replay: true``),
  a retry with a different body is rejected (422).
* Every successful write invalidates the workspace's cached reports and emits ``metrics.upserted``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_workspace
from app.db import get_db
from app.deps import get_cache
from app.ingest import IngestError, ingest
from app.models import Campaign, DailyMetric, IdempotencyKey, Workspace
from app.routers.campaigns import get_campaign_or_404
from app.schemas import BulkMetricsRequest, BulkMetricsResponse, MetricOut

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.post("/bulk", response_model=BulkMetricsResponse)
def bulk_upsert(
    payload: BulkMetricsRequest,
    response: Response,
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
    cache=Depends(get_cache),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    body_hash = hashlib.sha256(
        json.dumps([r.model_dump(mode="json", exclude_none=True) for r in payload.rows], sort_keys=True).encode()
    ).hexdigest()

    if idempotency_key:
        existing = db.get(IdempotencyKey, (ws.id, idempotency_key))
        if existing:
            if existing.request_hash != body_hash:
                raise HTTPException(status_code=422, detail="Idempotency-Key reused with a different payload")
            response.headers["Idempotent-Replayed"] = "true"
            data = json.loads(existing.response_json)
            data["idempotent_replay"] = True
            return data

    rows = [r.model_dump() for r in payload.rows]
    try:
        res = ingest(db, ws.id, rows, source="api")
    except IngestError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = {
        "received": res.received,
        "upserted": res.upserted,
        "campaigns_touched": res.campaigns_touched,
        "campaigns_created": res.campaigns_created,
        "idempotent_replay": False,
        "import_id": res.import_id,
    }
    if idempotency_key:
        db.add(
            IdempotencyKey(
                workspace_id=ws.id, key=idempotency_key, request_hash=body_hash, response_json=json.dumps(result)
            )
        )
    db.commit()
    cache.invalidate_workspace(ws.id)
    response.headers["Idempotent-Replayed"] = "false"
    return result


@router.get("", response_model=list[MetricOut])
def list_metrics(
    campaign_id: int | None = None,
    start: date | None = None,
    end: date | None = None,
    limit: int = Query(default=500, le=5000),
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
):
    stmt = select(DailyMetric).join(Campaign).where(Campaign.workspace_id == ws.id)
    if campaign_id:
        stmt = stmt.where(DailyMetric.campaign_id == campaign_id)
    if start:
        stmt = stmt.where(DailyMetric.day >= start)
    if end:
        stmt = stmt.where(DailyMetric.day <= end)
    return db.scalars(stmt.order_by(DailyMetric.day.desc(), DailyMetric.campaign_id).limit(limit)).all()


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_metrics(
    campaign_id: int,
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
    cache=Depends(get_cache),
):
    camp = get_campaign_or_404(db, ws.id, campaign_id)
    for m in list(camp.metrics):
        db.delete(m)
    db.commit()
    cache.invalidate_workspace(ws.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
