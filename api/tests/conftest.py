"""Shared fixtures: isolated DB per test (SQLite by default, PostgreSQL when DATABASE_URL set), fresh cache."""

import os
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app import db as dbmod
from app.cache import InMemoryCache
from app.db import Base, get_db, make_engine
from app.deps import get_cache, set_cache
from app.main import app

TEST_DB_URL = os.environ.get("DATABASE_URL", "sqlite://")


@pytest.fixture
def engine():
    eng = make_engine(TEST_DB_URL)
    from app import models  # noqa: F401

    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
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
def client(engine, cache, monkeypatch):
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    # lifespan would call init_db() on the module engine; point it at the test engine instead
    monkeypatch.setattr(dbmod, "engine", engine)
    app.dependency_overrides[get_db] = _override
    app.dependency_overrides[get_cache] = lambda: cache
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def account(client):
    r = client.post("/api/v1/accounts", json={"name": "Acme", "currency": "usd"})
    assert r.status_code == 201, r.text
    return r.json()


def make_campaign(client, account_id: int, channel: str, idx: int = 1, **kw) -> dict:
    body = {"channel": channel, "external_id": f"{channel}-{idx}", "name": f"{channel} #{idx}", "daily_budget": 100}
    body.update(kw)
    r = client.post(f"/api/v1/accounts/{account_id}/campaigns", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def metric_rows(
    campaign_id: int, days: int, spend: float, roas: float, end: date | None = None, spend_jitter: float = 0.0
) -> list[dict]:
    """Deterministic synthetic rows. spend_jitter spreads spend so a curve can be fitted."""
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


@pytest.fixture
def seeded(client, account):
    """Account with google/meta/amazon campaigns and 30 days of metrics."""
    acc_id = account["id"]
    camps = {
        "google": make_campaign(client, acc_id, "google"),
        "meta": make_campaign(client, acc_id, "meta"),
        "amazon": make_campaign(client, acc_id, "amazon"),
    }
    rows = (
        metric_rows(camps["google"]["id"], 30, 1000, 4.0, spend_jitter=0.4)
        + metric_rows(camps["meta"]["id"], 30, 800, 1.5, spend_jitter=0.4)
        + metric_rows(camps["amazon"]["id"], 30, 500, 3.0, spend_jitter=0.4)
    )
    r = client.post(f"/api/v1/accounts/{acc_id}/metrics/bulk", json={"rows": rows})
    assert r.status_code == 200, r.text
    return {"account": account, "campaigns": camps, "rows": rows}


@pytest.fixture
def raw_sql(db):
    def _run(sql: str, **params):
        res = db.execute(text(sql), params)
        if res.returns_rows:
            return res.all()
        db.commit()
        return []

    return _run
