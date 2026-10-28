"""Shared fixtures: isolated DB per test (file SQLite by default, PostgreSQL when DATABASE_URL is set),
fresh in-process cache, and an authenticated per-workspace client wrapper."""

import os
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app import db as dbmod
from app.cache import InMemoryCache
from app.config import get_settings
from app.db import Base, get_db, get_sessionmaker, init_db, make_engine
from app.deps import get_cache, set_cache
from app.main import app

API = "/api/v1"
FIXTURES = Path(__file__).parent / "fixtures"
PG_URL = os.environ.get("DATABASE_URL", "")
# The suite drops/creates tables: never point it at the production schema of a shared database.
if ("supabase" in PG_URL or "pooler" in PG_URL) and os.environ.get("DB_SCHEMA", "channelmix") == "channelmix":
    raise RuntimeError("refusing to run the test suite against Supabase without a throwaway DB_SCHEMA")


@pytest.fixture
def engine(tmp_path):
    url = PG_URL if PG_URL.startswith("postgresql") else f"sqlite:///{tmp_path}/test.db"
    eng = make_engine(url, pool="queue")
    from app import models  # noqa: F401

    Base.metadata.drop_all(eng)
    init_db(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def db(engine):
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    s = Session()
    yield s
    s.close()


@pytest.fixture
def cache():
    c = InMemoryCache()
    set_cache(c)
    yield c
    set_cache(None)


@pytest.fixture
def fast_sse(monkeypatch):
    """Shorten SSE timings so stream tests finish quickly."""
    s = get_settings()
    monkeypatch.setattr(s, "sse_max_seconds", 3.0)
    monkeypatch.setattr(s, "sse_heartbeat_seconds", 0.5)
    monkeypatch.setattr(s, "sse_poll_seconds", 0.05)
    return s


@pytest.fixture
def client(engine, cache, monkeypatch):
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    monkeypatch.setattr(dbmod, "engine", engine)
    app.dependency_overrides[get_db] = _override
    app.dependency_overrides[get_sessionmaker] = lambda: Session
    app.dependency_overrides[get_cache] = lambda: cache
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class WS:
    """Authenticated client for one workspace (adds X-Api-Key to every call)."""

    def __init__(self, client: TestClient, ws: dict):
        self.client = client
        self.ws = ws
        self.id = ws["id"]
        self.key = ws["api_key"]
        self.headers = {"X-Api-Key": ws["api_key"]}

    def _call(self, method, url, **kw):
        headers = {**self.headers, **kw.pop("headers", {})}
        return getattr(self.client, method)(url, headers=headers, **kw)

    def get(self, url, **kw):
        return self._call("get", url, **kw)

    def post(self, url, **kw):
        return self._call("post", url, **kw)

    def patch(self, url, **kw):
        return self._call("patch", url, **kw)

    def delete(self, url, **kw):
        return self._call("delete", url, **kw)

    def bulk(self, rows, key=None):
        headers = {"Idempotency-Key": key} if key else {}
        return self.post(f"{API}/metrics/bulk", json={"rows": rows}, headers=headers)


def make_workspace(client: TestClient, name: str = "Acme", email: str = "owner@acme-example.com") -> WS:
    r = client.post(f"{API}/workspaces", json={"name": name, "email": email})
    assert r.status_code == 201, r.text
    return WS(client, r.json())


@pytest.fixture
def ws(client) -> WS:
    return make_workspace(client)


@pytest.fixture
def other_ws(client) -> WS:
    return make_workspace(client, "Other Co", "other@other-example.com")


def make_campaign(ws: WS, channel: str, idx: int = 1, **kw) -> dict:
    body = {"channel": channel, "external_id": f"{channel}-{idx}", "name": f"{channel} #{idx}", "daily_budget": 100}
    body.update(kw)
    r = ws.post(f"{API}/campaigns", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def metric_rows(
    campaign_id: int, days: int, spend: float, roas: float, end: date | None = None, spend_jitter: float = 0.0
) -> list[dict]:
    """Deterministic synthetic rows for tests. spend_jitter spreads spend so a curve can be fitted."""
    end = end or date.today()
    rows = []
    for i in range(days):
        d = end - timedelta(days=days - 1 - i)
        s = spend * (1 + spend_jitter * ((i % 7) - 3) / 3)
        rows.append(
            {
                "campaign_id": campaign_id,
                "day": d.isoformat(),
                "impressions": 10_000,
                "clicks": 200,
                "conversions": 10,
                "spend": round(s, 2),
                "revenue": round(s * roas, 2),
            }
        )
    return rows


def seed_workspace(ws: WS, channels: dict[str, tuple[float, float]], days: int = 30) -> dict:
    camps, rows = {}, []
    for ch, (spend, roas) in channels.items():
        camps[ch] = make_campaign(ws, ch)
        rows += metric_rows(camps[ch]["id"], days, spend, roas, spend_jitter=0.4)
    r = ws.bulk(rows)
    assert r.status_code == 200, r.text
    return {"ws": ws, "campaigns": camps, "rows": rows}


@pytest.fixture
def seeded(ws):
    """Workspace with google/meta/amazon campaigns and 30 days of metrics."""
    return seed_workspace(ws, {"google": (1000.0, 4.0), "meta": (800.0, 1.5), "amazon": (500.0, 3.0)})


@pytest.fixture
def raw_sql(db):
    from app.db import table_prefix

    def _run(sql: str, **params):
        res = db.execute(text(sql.format(p=table_prefix(db.get_bind()))), params)
        if res.returns_rows:
            return res.all()
        db.commit()
        return []

    return _run


def upload(ws: WS, name: str, **form):
    data = {k: str(v).lower() if isinstance(v, bool) else str(v) for k, v in form.items()}
    with open(FIXTURES / name, "rb") as fh:
        return ws.post(f"{API}/imports/csv", files={"file": (name, fh, "text/csv")}, data=data)
