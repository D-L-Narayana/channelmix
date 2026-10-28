import re

from tests.conftest import API, make_campaign, make_workspace


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok" and r.json()["cache"] == "memory"
    assert r.json()["database"] in ("sqlite", "postgresql")


def test_openapi_is_versioned(client):
    r = client.get("/api/v1/openapi.json")
    assert r.status_code == 200
    assert all(p.startswith("/api/v1") or p == "/health" for p in r.json()["paths"])


# ---------------- workspaces ----------------
def test_create_workspace_returns_key_once(client):
    r = client.post(f"{API}/workspaces", json={"name": "Acme Retail", "email": "me@acme-example.com"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert re.fullmatch(r"cmx_[0-9a-f]{40}", body["api_key"])
    assert re.fullmatch(r"acme-retail-[0-9a-f]{4}", body["slug"])
    assert body["workspace_url"].endswith(f"/w/{body['slug']}?key={body['api_key']}")
    me = client.get(f"{API}/workspaces/me", headers={"X-Api-Key": body["api_key"]}).json()
    assert "api_key" not in me and me["slug"] == body["slug"]
    assert me["stats"] == {"campaigns": 0, "metric_rows": 0, "imports": 0, "first_day": None, "last_day": None}


def test_create_workspace_validation(client):
    assert client.post(f"{API}/workspaces", json={"name": "", "email": "a@b.co"}).status_code == 422
    assert client.post(f"{API}/workspaces", json={"name": "x", "email": "not-an-email"}).status_code == 422


def test_missing_or_invalid_key_is_401(client, ws):
    assert client.get(f"{API}/workspaces/me").status_code == 401
    assert client.get(f"{API}/workspaces/me", headers={"X-Api-Key": "cmx_" + "0" * 40}).status_code == 401
    assert client.get(f"{API}/workspaces/me", headers={"X-Api-Key": "garbage"}).status_code == 401
    assert client.get(f"{API}/campaigns").status_code == 401
    assert client.post(f"{API}/metrics/bulk", json={"rows": []}).status_code == 401
    assert client.get(f"{API}/reports/summary").status_code == 401
    assert client.get(f"{API}/stream").status_code == 401


def test_api_key_accepted_as_query_param(client, ws):
    r = client.get(f"{API}/workspaces/me", params={"api_key": ws.key})
    assert r.status_code == 200 and r.json()["id"] == ws.id


def test_me_stats_reflect_data(ws):
    c = make_campaign(ws, "google")
    ws.bulk([{"campaign_id": c["id"], "day": "2025-01-01", "spend": 1}, {"campaign_id": c["id"], "day": "2025-01-03"}])
    stats = ws.get(f"{API}/workspaces/me").json()["stats"]
    assert stats == {
        "campaigns": 1,
        "metric_rows": 2,
        "imports": 1,
        "first_day": "2025-01-01",
        "last_day": "2025-01-03",
    }


# ---------------- campaigns ----------------
def test_create_campaign_per_channel(ws):
    for ch in ("google", "meta", "amazon", "linkedin", "other"):
        c = make_campaign(ws, ch)
        assert c["channel"] == ch and c["workspace_id"] == ws.id
    assert len(ws.get(f"{API}/campaigns").json()) == 5


def test_create_campaign_invalid_channel(ws):
    r = ws.post(f"{API}/campaigns", json={"channel": "tiktok", "external_id": "1", "name": "x"})
    assert r.status_code == 422


def test_create_campaign_duplicate_external_id_conflicts(ws):
    make_campaign(ws, "google", 1)
    r = ws.post(f"{API}/campaigns", json={"channel": "google", "external_id": "google-1", "name": "dup"})
    assert r.status_code == 409


def test_same_external_id_allowed_in_other_workspace(ws, other_ws):
    make_campaign(ws, "google", 1)
    make_campaign(other_ws, "google", 1)  # no 409: uniqueness is per workspace


def test_campaign_filters(ws):
    make_campaign(ws, "google", 1)
    make_campaign(ws, "google", 2, status="paused")
    make_campaign(ws, "meta", 1)
    r = ws.get(f"{API}/campaigns", params={"channel": "google"})
    assert {c["channel"] for c in r.json()} == {"google"} and len(r.json()) == 2
    r = ws.get(f"{API}/campaigns", params={"status": "paused"})
    assert [c["external_id"] for c in r.json()] == ["google-2"]


def test_update_and_delete_campaign(ws):
    c = make_campaign(ws, "meta")
    r = ws.patch(f"{API}/campaigns/{c['id']}", json={"status": "paused", "daily_budget": 55.5})
    assert r.status_code == 200
    assert r.json()["status"] == "paused" and float(r.json()["daily_budget"]) == 55.5
    assert ws.delete(f"{API}/campaigns/{c['id']}").status_code == 204
    assert ws.get(f"{API}/campaigns/{c['id']}").status_code == 404


def test_campaign_not_found(ws):
    assert ws.get(f"{API}/campaigns/999").status_code == 404
    assert ws.patch(f"{API}/campaigns/999", json={"name": "x"}).status_code == 404
    assert ws.delete(f"{API}/campaigns/999").status_code == 404


def test_campaign_isolated_between_workspaces(ws, other_ws):
    c = make_campaign(ws, "google")
    assert other_ws.get(f"{API}/campaigns/{c['id']}").status_code == 404
    assert other_ws.patch(f"{API}/campaigns/{c['id']}", json={"name": "hijack"}).status_code == 404
    assert other_ws.delete(f"{API}/campaigns/{c['id']}").status_code == 404
    assert other_ws.get(f"{API}/campaigns").json() == []
    assert ws.get(f"{API}/campaigns/{c['id']}").json()["name"] == c["name"]


def test_delete_campaign_cascades_metrics(ws, db):
    from sqlalchemy import func, select

    from app.models import DailyMetric

    c = make_campaign(ws, "google")
    ws.bulk([{"campaign_id": c["id"], "day": "2025-01-01", "spend": 1}])
    ws.delete(f"{API}/campaigns/{c['id']}")
    assert db.scalar(select(func.count()).select_from(DailyMetric)) == 0


def test_campaign_changes_emit_events(ws):
    c = make_campaign(ws, "google")
    ws.patch(f"{API}/campaigns/{c['id']}", json={"status": "paused"})
    ws.delete(f"{API}/campaigns/{c['id']}")
    evs = ws.get(f"{API}/events", params={"after": 0}).json()
    assert [e["type"] for e in evs] == ["campaign.changed"] * 3
    assert [e["payload"]["action"] for e in evs] == ["created", "updated", "deleted"]


def test_request_id_header_is_returned_and_echoed(client):
    r = client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert r.headers["X-Request-ID"] == "abc-123"
    assert len(client.get("/health").headers["X-Request-ID"]) == 32


def test_two_workspaces_get_distinct_keys(client):
    a, b = make_workspace(client, "A"), make_workspace(client, "A")
    assert a.key != b.key and a.ws["slug"] != b.ws["slug"]
