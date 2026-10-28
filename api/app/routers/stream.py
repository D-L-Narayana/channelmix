"""Live change feed: ``GET /stream`` (Server-Sent Events) and ``GET /events`` (polling fallback).

Events are persisted (``events`` table) so the feed works across serverless instances: the stream simply
tails the table for the caller's workspace. On Vercel a function cannot run forever, so the response is
closed after ``SSE_MAX_SECONDS`` (25s) and the browser's ``EventSource`` reconnects, sending
``Last-Event-ID`` — nothing is lost.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import events
from app.auth import current_workspace
from app.config import get_settings
from app.db import get_db, get_sessionmaker
from app.models import Workspace
from app.schemas import EventOut

router = APIRouter(tags=["events"])

REPLAY_CAP = 500


def _sse(ev: dict) -> str:
    return f"id: {ev['id']}\nevent: {ev['type']}\ndata: {json.dumps(ev, default=str)}\n\n"


@router.get("/stream", summary="Server-Sent Events feed for the workspace")
async def stream(
    request: Request,
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
    session_factory=Depends(get_sessionmaker),
    last_event_id_header: str | None = Header(default=None, alias="Last-Event-ID"),
    last_event_id: int | None = Query(default=None, ge=0),
):
    s = get_settings()
    ws_id = ws.id
    cursor_raw = last_event_id if last_event_id is not None else last_event_id_header
    try:
        cursor = int(cursor_raw) if cursor_raw is not None else None
    except ValueError:
        cursor = None
    if cursor is None:
        cursor = events.latest_id(db, ws_id)
    db.close()

    def fetch(after: int) -> list[dict]:
        with session_factory() as session:
            return [events.to_dict(e) for e in events.fetch_after(session, ws_id, after, limit=REPLAY_CAP)]

    async def gen():
        nonlocal cursor
        ready = {"last_event_id": cursor, "workspace_id": ws_id, "max_seconds": s.sse_max_seconds}
        yield f"retry: 2000\nevent: ready\nid: {cursor}\ndata: {json.dumps(ready)}\n\n"
        started = last_beat = time.monotonic()
        while True:
            if await request.is_disconnected():
                return
            batch = await run_in_threadpool(fetch, cursor)
            for ev in batch:
                cursor = ev["id"]
                yield _sse(ev)
            now = time.monotonic()
            if batch:
                last_beat = now
            if now - started >= s.sse_max_seconds:
                yield ": reconnect\n\n"
                return
            if now - last_beat >= s.sse_heartbeat_seconds:
                yield ": ping\n\n"
                last_beat = now
            await asyncio.sleep(s.sse_poll_seconds)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/events", response_model=list[EventOut], summary="Polling fallback for /stream")
def list_events(
    request: Request,
    response: Response,
    after: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=REPLAY_CAP),
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
):
    rows = [events.to_dict(e) for e in events.fetch_after(db, ws.id, after, limit)]
    last = rows[-1]["id"] if rows else after
    etag = 'W/"' + hashlib.sha1(f"{ws.id}:{after}:{last}:{len(rows)}".encode()).hexdigest()[:16] + '"'
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "no-cache"
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return rows
