"""Public signup must be throttled and tenants quota-bound."""

from app.config import get_settings


def test_signup_throttled_per_ip(client):
    s = get_settings()
    limit = s.signup_per_ip_per_hour
    codes = [
        client.post("/api/v1/workspaces", json={"name": f"t{i}", "email": f"t{i}@example.com"}).status_code
        for i in range(limit + 2)
    ]
    assert codes[:limit] == [201] * limit
    assert codes[limit:] == [429, 429]


def test_quota_blocks_oversized_import(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "max_metric_rows_per_workspace", 2)
    ws = client.post("/api/v1/workspaces", json={"name": "q", "email": "q@example.com"}).json()
    h = {"X-Api-Key": ws["api_key"]}
    rows = [
        {
            "channel": "google",
            "external_id": "c1",
            "campaign_name": "c1",
            "day": f"2025-01-0{d}",
            "spend": 1,
            "impressions": 1,
            "clicks": 1,
            "conversions": 0,
            "revenue": 0,
        }
        for d in (1, 2, 3)
    ]
    r = client.post("/api/v1/metrics/bulk", json={"rows": rows}, headers=h)
    assert r.status_code == 413
