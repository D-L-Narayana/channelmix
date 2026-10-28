"""Append-only workspace event feed (backs SSE + polling)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Event

METRICS_UPSERTED = "metrics.upserted"
CAMPAIGN_CHANGED = "campaign.changed"
IMPORT_COMPLETED = "import.completed"


def emit(db: Session, workspace_id: int, type_: str, payload: dict[str, Any]) -> Event:
    """Add an event to the current transaction (committed together with the change it describes)."""
    ev = Event(workspace_id=workspace_id, type=type_, payload_json=json.dumps(payload, default=str))
    db.add(ev)
    db.flush()
    return ev


def to_dict(ev: Event) -> dict[str, Any]:
    return {
        "id": ev.id,
        "type": ev.type,
        "created_at": ev.created_at.isoformat() if ev.created_at else None,
        "payload": json.loads(ev.payload_json or "{}"),
    }


def latest_id(db: Session, workspace_id: int) -> int:
    return int(db.scalar(select(func.max(Event.id)).where(Event.workspace_id == workspace_id)) or 0)


def fetch_after(db: Session, workspace_id: int, after_id: int, limit: int = 100) -> list[Event]:
    stmt = select(Event).where(Event.workspace_id == workspace_id, Event.id > after_id).order_by(Event.id).limit(limit)
    return list(db.scalars(stmt).all())
