"""Idempotent bulk metric ingestion.

* ``POST /accounts/{id}/metrics/bulk`` upserts rows on the natural key
  (campaign_id, day) with a single ``INSERT ... ON CONFLICT DO UPDATE`` per chunk.
* An ``Idempotency-Key`` header makes retries safe: the first completed request
  stores its response; a retry with the same key + same body replays it
  (``idempotent_replay: true``), a retry with a different body is rejected (422).
* Every successful write invalidates the account's cached reports.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_cache
from app.models import Campaign, DailyMetric, IdempotencyKey, utcnow
from app.routers.accounts import get_account_or_404
from app.schemas import BulkMetricsRequest, BulkMetricsResponse, MetricOut

router = APIRouter(prefix="/accounts/{account_id}/metrics", tags=["metrics"])

CHUNK = 2000
UPDATE_COLS = ("impressions", "clicks", "conversions", "spend", "revenue")


def _insert_for(dialect: str):
    return postgresql.insert if dialect == "postgresql" else sqlite.insert


def upsert_metrics(db: Session, rows: list[dict]) -> int:
    """Chunked ON CONFLICT upsert. Returns number of rows written."""
    insert = _insert_for(db.get_bind().dialect.name)
    written = 0
    # de-duplicate within the batch (last one wins) - ON CONFLICT cannot touch a row twice in one statement
    dedup: dict[tuple[int, date], dict] = {}
    for r in rows:
        dedup[(r["campaign_id"], r["day"])] = r
    unique_rows = list(dedup.values())
    now = utcnow()
    for i in range(0, len(unique_rows), CHUNK):
        chunk = [{**r, "updated_at": now} for r in unique_rows[i : i + CHUNK]]
        stmt = insert(DailyMetric)
        stmt = stmt.on_conflict_do_update(
            index_elements=["campaign_id", "day"],
            set_={c: getattr(stmt.excluded, c) for c in (*UPDATE_COLS, "updated_at")},
        )
        # executemany -> SQLAlchemy "insertmanyvalues" batches this into multi-row INSERT ... ON CONFLICT statements
        db.execute(stmt, chunk)
        written += len(chunk)
    return written


@router.post("/bulk", response_model=BulkMetricsResponse)
def bulk_upsert(
    account_id: int,
    payload: BulkMetricsRequest,
    response: Response,
    db: Session = Depends(get_db),
    cache=Depends(get_cache),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    get_account_or_404(db, account_id)
    body_hash = hashlib.sha256(
        json.dumps([r.model_dump(mode="json") for r in payload.rows], sort_keys=True).encode()
    ).hexdigest()

    if idempotency_key:
        existing = db.get(IdempotencyKey, idempotency_key)
        if existing:
            if existing.request_hash != body_hash:
                raise HTTPException(status_code=422, detail="Idempotency-Key reused with a different payload")
            response.headers["Idempotent-Replayed"] = "true"
            data = json.loads(existing.response_json)
            data["idempotent_replay"] = True
            return data

    campaign_ids = {r.campaign_id for r in payload.rows}
    owned = set(
        db.scalars(select(Campaign.id).where(Campaign.account_id == account_id, Campaign.id.in_(campaign_ids))).all()
    )
    unknown = campaign_ids - owned
    if unknown:
        raise HTTPException(status_code=422, detail=f"campaigns not in account: {sorted(unknown)[:10]}")

    rows = [r.model_dump() for r in payload.rows]
    written = upsert_metrics(db, rows)
    result = {
        "received": len(rows),
        "upserted": written,
        "campaigns_touched": len(campaign_ids),
        "idempotent_replay": False,
    }
    if idempotency_key:
        db.add(
            IdempotencyKey(
                key=idempotency_key, account_id=account_id, request_hash=body_hash, response_json=json.dumps(result)
            )
        )
    db.commit()
    cache.invalidate_account(account_id)
    response.headers["Idempotent-Replayed"] = "false"
    return result


@router.get("", response_model=list[MetricOut])
def list_metrics(
    account_id: int,
    campaign_id: int | None = None,
    start: date | None = None,
    end: date | None = None,
    limit: int = Query(default=500, le=5000),
    db: Session = Depends(get_db),
):
    get_account_or_404(db, account_id)
    stmt = select(DailyMetric).join(Campaign).where(Campaign.account_id == account_id)
    if campaign_id:
        stmt = stmt.where(DailyMetric.campaign_id == campaign_id)
    if start:
        stmt = stmt.where(DailyMetric.day >= start)
    if end:
        stmt = stmt.where(DailyMetric.day <= end)
    return db.scalars(stmt.order_by(DailyMetric.day.desc(), DailyMetric.campaign_id).limit(limit)).all()


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_metrics(
    account_id: int,
    campaign_id: int,
    db: Session = Depends(get_db),
    cache=Depends(get_cache),
):
    get_account_or_404(db, account_id)
    camp = db.get(Campaign, campaign_id)
    if not camp or camp.account_id != account_id:
        raise HTTPException(status_code=404, detail="campaign not found")
    for m in list(camp.metrics):
        db.delete(m)
    db.commit()
    cache.invalidate_account(account_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
