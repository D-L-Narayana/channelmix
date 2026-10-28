"""Workspace resolution from the API key.

Keys look like ``cmx_<40 hex>``; only the SHA-256 hash is stored. Every scoped endpoint depends on
``current_workspace`` and must filter by ``workspace.id`` — a foreign id therefore surfaces as 404.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import unicodedata

from fastapi import Depends, Header, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Workspace

KEY_PREFIX = "cmx_"


def generate_api_key() -> str:
    return KEY_PREFIX + secrets.token_hex(20)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.strip().encode()).hexdigest()


def slugify(value: str, max_len: int = 60) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (value or "workspace")[:max_len].strip("-")


def new_slug(name: str) -> str:
    return f"{slugify(name)}-{secrets.token_hex(2)}"


def current_workspace(
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
    api_key: str | None = Query(default=None, description="Alternative to X-Api-Key (for EventSource)"),
) -> Workspace:
    key = x_api_key or api_key
    if not key or not key.startswith(KEY_PREFIX):
        raise HTTPException(status_code=401, detail="missing or invalid API key")
    digest = hash_api_key(key)
    ws = db.scalar(select(Workspace).where(Workspace.api_key_hash == digest))
    if ws is None or not hmac.compare_digest(ws.api_key_hash, digest):
        raise HTTPException(status_code=401, detail="missing or invalid API key")
    request.state.workspace_id = ws.id
    return ws
