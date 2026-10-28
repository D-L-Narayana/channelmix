"""Shared ingestion core used by the bulk API, CSV imports and the sample dataset.

* resolves campaigns (by id, or by channel + external_id with auto-create)
* chunked ``INSERT ... ON CONFLICT (campaign_id, day) DO UPDATE``
* writes the ``imports`` audit row and the ``events`` feed entries in the same transaction
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from app import events
from app.models import Campaign, Channel, DailyMetric, Import, utcnow

CHUNK = 2000
METRIC_COLS = ("impressions", "clicks", "conversions", "spend", "revenue")


class IngestError(ValueError):
    pass


@dataclass
class IngestResult:
    received: int
    upserted: int
    campaigns_touched: int
    campaigns_created: int
    first_day: date | None
    last_day: date | None
    import_id: int | None = None
    warnings: list[str] = field(default_factory=list)


def _insert_for(dialect: str):
    return postgresql.insert if dialect == "postgresql" else sqlite.insert


def upsert_metrics(db: Session, rows: list[dict], aggregate: bool = False) -> int:
    """Chunked ON CONFLICT upsert. ``rows`` need ``campaign_id`` + ``day`` (+ metric cols).

    Duplicates of the same (campaign_id, day) inside the batch are collapsed first (ON CONFLICT cannot
    touch a row twice in one statement): last-one-wins by default, summed when ``aggregate`` is set
    (CSV exports segmented by device/network/etc.). Returns the number of rows written.
    """
    insert = _insert_for(db.get_bind().dialect.name)
    dedup: dict[tuple[int, date], dict] = {}
    for r in rows:
        k = (r["campaign_id"], r["day"])
        clean = {"campaign_id": r["campaign_id"], "day": r["day"]}
        for c in METRIC_COLS:
            clean[c] = r.get(c) or 0
        if aggregate and k in dedup:
            prev = dedup[k]
            for c in METRIC_COLS:
                prev[c] = prev[c] + clean[c]
        else:
            dedup[k] = clean
    unique_rows = list(dedup.values())
    now = utcnow()
    written = 0
    for i in range(0, len(unique_rows), CHUNK):
        chunk = [{**r, "updated_at": now} for r in unique_rows[i : i + CHUNK]]
        stmt = insert(DailyMetric)
        stmt = stmt.on_conflict_do_update(
            index_elements=["campaign_id", "day"],
            set_={c: getattr(stmt.excluded, c) for c in (*METRIC_COLS, "updated_at")},
        )
        db.execute(stmt, chunk)
        written += len(chunk)
    return written


def resolve_campaigns(db: Session, workspace_id: int, rows: list[dict]) -> tuple[list[dict], int, set[int]]:
    """Attach ``campaign_id`` to every row. Creates campaigns referenced by (channel, external_id).

    Raises IngestError when a ``campaign_id`` is not owned by the workspace.
    """
    by_id = {r["campaign_id"] for r in rows if r.get("campaign_id") is not None}
    if by_id:
        owned = set(
            db.scalars(select(Campaign.id).where(Campaign.workspace_id == workspace_id, Campaign.id.in_(by_id))).all()
        )
        unknown = by_id - owned
        if unknown:
            raise IngestError(f"campaigns not in workspace: {sorted(unknown)[:10]}")

    keyed = [r for r in rows if r.get("campaign_id") is None]
    created = 0
    if keyed:
        wanted: dict[tuple[str, str], str] = {}
        for r in keyed:
            ch = r["channel"].value if isinstance(r["channel"], Channel) else str(r["channel"])
            key = (ch, str(r["external_id"])[:100])
            name = (r.get("campaign_name") or r["external_id"] or "")[:200]
            wanted.setdefault(key, name)
        existing = {
            (c.channel.value if isinstance(c.channel, Channel) else c.channel, c.external_id): c.id
            for c in db.scalars(
                select(Campaign).where(
                    Campaign.workspace_id == workspace_id,
                    Campaign.external_id.in_({k[1] for k in wanted}),
                )
            )
        }
        for key, name in wanted.items():
            if key not in existing:
                camp = Campaign(
                    workspace_id=workspace_id,
                    channel=Channel(key[0]),
                    external_id=key[1],
                    name=name or key[1],
                )
                db.add(camp)
                db.flush()
                existing[key] = camp.id
                created += 1
                events.emit(
                    db,
                    workspace_id,
                    events.CAMPAIGN_CHANGED,
                    {"campaign_id": camp.id, "action": "created", "channel": key[0], "name": camp.name},
                )
        for r in keyed:
            ch = r["channel"].value if isinstance(r["channel"], Channel) else str(r["channel"])
            r["campaign_id"] = existing[(ch, str(r["external_id"])[:100])]
    touched = {r["campaign_id"] for r in rows}
    return rows, created, touched


def ingest(
    db: Session,
    workspace_id: int,
    rows: list[dict],
    *,
    source: str,
    filename: str | None = None,
    aggregate: bool = False,
    warnings: list[str] | None = None,
    detail: dict | None = None,
) -> IngestResult:
    """Resolve campaigns, upsert metrics, write audit + events. Caller commits.

    Enforces a per-workspace metric-row quota so one tenant cannot exhaust shared storage.
    """
    from fastapi import HTTPException

    from app.config import get_settings

    quota = get_settings().max_metric_rows_per_workspace
    current = (
        db.scalar(
            select(func.count(DailyMetric.id))
            .join(Campaign, Campaign.id == DailyMetric.campaign_id)
            .where(Campaign.workspace_id == workspace_id)
        )
        or 0
    )
    if current + len(rows) > quota:
        raise HTTPException(
            413,
            detail=f"Workspace metric-row quota ({quota:,}) would be exceeded; current {current:,}, incoming {len(rows):,}.",
        )
    rows, created, touched = resolve_campaigns(db, workspace_id, rows)
    written = upsert_metrics(db, rows, aggregate=aggregate)
    days = [r["day"] for r in rows]
    first_day, last_day = (min(days), max(days)) if days else (None, None)
    imp = Import(
        workspace_id=workspace_id,
        source=source,
        filename=filename,
        status="completed",
        rows_received=len(rows),
        rows_upserted=written,
        campaigns_created=created,
        warnings_json=json.dumps(warnings or []),
        detail_json=json.dumps(
            {
                **(detail or {}),
                "campaigns_touched": len(touched),
                "first_day": first_day.isoformat() if first_day else None,
                "last_day": last_day.isoformat() if last_day else None,
            },
            default=str,
        ),
    )
    db.add(imp)
    db.flush()
    events.emit(
        db,
        workspace_id,
        events.METRICS_UPSERTED,
        {
            "rows": written,
            "campaigns_touched": len(touched),
            "campaigns_created": created,
            "first_day": first_day,
            "last_day": last_day,
            "import_id": imp.id,
            "source": source,
        },
    )
    if source != "api":
        events.emit(
            db,
            workspace_id,
            events.IMPORT_COMPLETED,
            {
                "import_id": imp.id,
                "source": source,
                "filename": filename,
                "rows_upserted": written,
                "campaigns_created": created,
                "status": "completed",
            },
        )
    return IngestResult(
        received=len(rows),
        upserted=written,
        campaigns_touched=len(touched),
        campaigns_created=created,
        first_day=first_day,
        last_day=last_day,
        import_id=imp.id,
        warnings=list(warnings or []),
    )


def to_decimal(v) -> Decimal:
    return v if isinstance(v, Decimal) else Decimal(str(v or 0))
