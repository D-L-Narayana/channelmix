from datetime import date

from tests.conftest import make_campaign, metric_rows

API = "/api/v1"


def _bulk(client, aid, rows, key=None):
    headers = {"Idempotency-Key": key} if key else {}
    return client.post(f"{API}/accounts/{aid}/metrics/bulk", json={"rows": rows}, headers=headers)


def test_bulk_insert_then_list(client, account):
    aid = account["id"]
    c = make_campaign(client, aid, "google")
    rows = metric_rows(c["id"], 5, 100, 3.0)
    r = _bulk(client, aid, rows)
    assert r.status_code == 200
    assert r.json() == {"received": 5, "upserted": 5, "campaigns_touched": 1, "idempotent_replay": False}
    listed = client.get(f"{API}/accounts/{aid}/metrics", params={"campaign_id": c["id"]}).json()
    assert len(listed) == 5 and float(listed[0]["revenue"]) == 300.0


def test_bulk_upsert_updates_existing_rows_without_duplicates(client, account, raw_sql):
    aid = account["id"]
    c = make_campaign(client, aid, "google")
    rows = metric_rows(c["id"], 10, 100, 3.0)
    _bulk(client, aid, rows)
    # re-send same days with corrected spend
    for row in rows:
        row["spend"] = 250.0
    r = _bulk(client, aid, rows)
    assert r.status_code == 200 and r.json()["upserted"] == 10
    [(count,)] = raw_sql("SELECT COUNT(*) FROM daily_metrics")
    [(total,)] = raw_sql("SELECT SUM(spend) FROM daily_metrics")
    assert count == 10
    assert float(total) == 2500.0


def test_bulk_dedupes_within_batch_last_wins(client, account):
    aid = account["id"]
    c = make_campaign(client, aid, "meta")
    d = date(2024, 1, 1).isoformat()
    rows = [
        {"campaign_id": c["id"], "day": d, "spend": 10, "revenue": 1},
        {"campaign_id": c["id"], "day": d, "spend": 20, "revenue": 2},
    ]
    r = _bulk(client, aid, rows)
    assert r.json()["received"] == 2 and r.json()["upserted"] == 1
    listed = client.get(f"{API}/accounts/{aid}/metrics").json()
    assert len(listed) == 1 and float(listed[0]["spend"]) == 20


def test_idempotency_key_replays_response(client, account, raw_sql):
    aid = account["id"]
    c = make_campaign(client, aid, "amazon")
    rows = metric_rows(c["id"], 7, 50, 2.0)
    r1 = _bulk(client, aid, rows, key="job-42")
    assert r1.headers["Idempotent-Replayed"] == "false"
    # mutate DB so we can prove the replay did not re-run the write
    raw_sql("UPDATE daily_metrics SET spend = 0")
    r2 = _bulk(client, aid, rows, key="job-42")
    assert r2.status_code == 200
    assert r2.headers["Idempotent-Replayed"] == "true"
    assert r2.json()["idempotent_replay"] is True
    assert r2.json()["upserted"] == 7


def test_idempotency_key_with_different_payload_rejected(client, account):
    aid = account["id"]
    c = make_campaign(client, aid, "amazon")
    _bulk(client, aid, metric_rows(c["id"], 3, 50, 2.0), key="k1")
    r = _bulk(client, aid, metric_rows(c["id"], 3, 99, 2.0), key="k1")
    assert r.status_code == 422
    assert "Idempotency-Key" in r.json()["detail"]


def test_bulk_rejects_foreign_campaign(client):
    a1 = client.post(f"{API}/accounts", json={"name": "A"}).json()
    a2 = client.post(f"{API}/accounts", json={"name": "B"}).json()
    c = make_campaign(client, a1["id"], "google")
    r = _bulk(client, a2["id"], metric_rows(c["id"], 2, 10, 1.0))
    assert r.status_code == 422
    assert "not in account" in r.json()["detail"]


def test_bulk_validation_errors(client, account):
    aid = account["id"]
    assert _bulk(client, aid, []).status_code == 422
    c = make_campaign(client, aid, "google")
    bad = [{"campaign_id": c["id"], "day": "2024-01-01", "spend": -5}]
    assert _bulk(client, aid, bad).status_code == 422


def test_bulk_unknown_account(client):
    assert _bulk(client, 12345, [{"campaign_id": 1, "day": "2024-01-01"}]).status_code == 404


def test_bulk_large_batch_spans_chunks(client, account):
    aid = account["id"]
    c = make_campaign(client, aid, "google")
    rows = metric_rows(c["id"], 2500, 10, 2.0)  # > CHUNK size
    r = _bulk(client, aid, rows)
    assert r.status_code == 200 and r.json()["upserted"] == 2500


def test_bulk_invalidates_report_cache(client, seeded, cache):
    aid = seeded["account"]["id"]
    client.get(f"{API}/accounts/{aid}/reports/channel-mix")
    assert client.get(f"{API}/accounts/{aid}/reports/channel-mix").headers["X-Cache"] == "HIT"
    _bulk(client, aid, seeded["rows"][:1])
    assert client.get(f"{API}/accounts/{aid}/reports/channel-mix").headers["X-Cache"] == "MISS"


def test_delete_metrics_for_campaign(client, account):
    aid = account["id"]
    c = make_campaign(client, aid, "meta")
    _bulk(client, aid, metric_rows(c["id"], 4, 10, 2.0))
    assert client.delete(f"{API}/accounts/{aid}/metrics", params={"campaign_id": c["id"]}).status_code == 204
    assert client.get(f"{API}/accounts/{aid}/metrics").json() == []
