from tests.conftest import make_campaign

API = "/api/v1"


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["cache"] == "memory"


def test_openapi_is_versioned(client):
    r = client.get("/api/v1/openapi.json")
    assert r.status_code == 200
    assert all(p.startswith("/api/v1") or p == "/health" for p in r.json()["paths"])


def test_create_account_uppercases_currency(client):
    r = client.post(f"{API}/accounts", json={"name": "Acme", "currency": "eur"})
    assert r.status_code == 201
    assert r.json()["currency"] == "EUR"
    assert r.json()["id"] > 0


def test_create_account_validation(client):
    assert client.post(f"{API}/accounts", json={"name": ""}).status_code == 422
    assert client.post(f"{API}/accounts", json={"name": "x", "currency": "TOOLONG"}).status_code == 422


def test_list_get_update_delete_account(client, account):
    aid = account["id"]
    assert [a["id"] for a in client.get(f"{API}/accounts").json()] == [aid]
    assert client.get(f"{API}/accounts/{aid}").json()["name"] == "Acme"
    r = client.patch(f"{API}/accounts/{aid}", json={"name": "Acme Corp"})
    assert r.status_code == 200 and r.json()["name"] == "Acme Corp"
    assert client.delete(f"{API}/accounts/{aid}").status_code == 204
    assert client.get(f"{API}/accounts/{aid}").status_code == 404


def test_account_not_found(client):
    assert client.get(f"{API}/accounts/999").status_code == 404
    assert client.patch(f"{API}/accounts/999", json={"name": "x"}).status_code == 404
    assert client.delete(f"{API}/accounts/999").status_code == 404


def test_create_campaign_per_channel(client, account):
    aid = account["id"]
    for ch in ("google", "meta", "amazon"):
        c = make_campaign(client, aid, ch)
        assert c["channel"] == ch and c["account_id"] == aid
    assert len(client.get(f"{API}/accounts/{aid}/campaigns").json()) == 3


def test_create_campaign_invalid_channel(client, account):
    r = client.post(
        f"{API}/accounts/{account['id']}/campaigns",
        json={"channel": "tiktok", "external_id": "1", "name": "x"},
    )
    assert r.status_code == 422


def test_create_campaign_duplicate_external_id_conflicts(client, account):
    aid = account["id"]
    make_campaign(client, aid, "google", 1)
    r = client.post(
        f"{API}/accounts/{aid}/campaigns",
        json={"channel": "google", "external_id": "google-1", "name": "dup"},
    )
    assert r.status_code == 409


def test_campaign_filter_by_channel(client, account):
    aid = account["id"]
    make_campaign(client, aid, "google", 1)
    make_campaign(client, aid, "google", 2)
    make_campaign(client, aid, "meta", 1)
    r = client.get(f"{API}/accounts/{aid}/campaigns", params={"channel": "google"})
    assert {c["channel"] for c in r.json()} == {"google"} and len(r.json()) == 2


def test_update_and_delete_campaign(client, account):
    aid = account["id"]
    c = make_campaign(client, aid, "meta")
    r = client.patch(f"{API}/accounts/{aid}/campaigns/{c['id']}", json={"status": "paused", "daily_budget": 55.5})
    assert r.status_code == 200
    assert r.json()["status"] == "paused" and float(r.json()["daily_budget"]) == 55.5
    assert client.delete(f"{API}/accounts/{aid}/campaigns/{c['id']}").status_code == 204
    assert client.get(f"{API}/accounts/{aid}/campaigns/{c['id']}").status_code == 404


def test_campaign_scoped_to_account(client):
    a1 = client.post(f"{API}/accounts", json={"name": "A"}).json()
    a2 = client.post(f"{API}/accounts", json={"name": "B"}).json()
    c = make_campaign(client, a1["id"], "google")
    assert client.get(f"{API}/accounts/{a2['id']}/campaigns/{c['id']}").status_code == 404


def test_delete_account_cascades_campaigns(client, account, db):
    from sqlalchemy import func, select

    from app.models import Campaign

    aid = account["id"]
    make_campaign(client, aid, "google")
    client.delete(f"{API}/accounts/{aid}")
    assert db.scalar(select(func.count()).select_from(Campaign)) == 0


def test_request_id_header_is_returned_and_echoed(client):
    r = client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert r.headers["X-Request-ID"] == "abc-123"
    r2 = client.get("/health")
    assert len(r2.headers["X-Request-ID"]) == 32
