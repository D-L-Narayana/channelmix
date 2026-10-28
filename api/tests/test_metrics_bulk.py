from datetime import date

from tests.conftest import API, make_campaign, metric_rows


def test_bulk_insert_then_list(ws):
    c = make_campaign(ws, "google")
    r = ws.bulk(metric_rows(c["id"], 5, 100, 3.0))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["received"] == 5 and body["upserted"] == 5 and body["campaigns_touched"] == 1
    assert body["campaigns_created"] == 0 and body["idempotent_replay"] is False and body["import_id"]
    listed = ws.get(f"{API}/metrics", params={"campaign_id": c["id"]}).json()
    assert len(listed) == 5 and float(listed[0]["revenue"]) == 300.0


def test_bulk_auto_creates_campaigns_by_channel_and_external_id(ws):
    rows = [
        {"channel": "google", "external_id": "brand", "campaign_name": "Brand", "day": "2025-10-01", "spend": 10},
        {"channel": "google", "external_id": "brand", "day": "2025-10-02", "spend": 11},
        {"channel": "meta", "external_id": "brand", "day": "2025-10-01", "spend": 5},  # same ext id, other channel
    ]
    r = ws.bulk(rows)
    assert r.status_code == 200, r.text
    assert r.json()["campaigns_created"] == 2 and r.json()["upserted"] == 3
    camps = {(c["channel"], c["external_id"]): c for c in ws.get(f"{API}/campaigns").json()}
    assert set(camps) == {("google", "brand"), ("meta", "brand")}
    assert camps[("google", "brand")]["name"] == "Brand" and camps[("meta", "brand")]["name"] == "brand"
    # second push reuses them
    r = ws.bulk([{"channel": "google", "external_id": "brand", "day": "2025-10-03", "spend": 12}])
    assert r.json()["campaigns_created"] == 0


def test_bulk_row_needs_identity(ws):
    r = ws.bulk([{"day": "2025-10-01", "spend": 1}])
    assert r.status_code == 422
    r = ws.bulk([{"channel": "google", "day": "2025-10-01"}])  # external_id missing
    assert r.status_code == 422


def test_bulk_upsert_updates_existing_rows_without_duplicates(ws, raw_sql):
    c = make_campaign(ws, "google")
    rows = metric_rows(c["id"], 10, 100, 3.0)
    ws.bulk(rows)
    for row in rows:
        row["spend"] = 250.0
    r = ws.bulk(rows)
    assert r.status_code == 200 and r.json()["upserted"] == 10
    [(count,)] = raw_sql("SELECT COUNT(*) FROM {p}daily_metrics")
    [(total,)] = raw_sql("SELECT SUM(spend) FROM {p}daily_metrics")
    assert count == 10 and float(total) == 2500.0


def test_bulk_dedupes_within_batch_last_wins(ws):
    c = make_campaign(ws, "meta")
    d = date(2024, 1, 1).isoformat()
    rows = [
        {"campaign_id": c["id"], "day": d, "spend": 10, "revenue": 1},
        {"campaign_id": c["id"], "day": d, "spend": 20, "revenue": 2},
    ]
    r = ws.bulk(rows)
    assert r.json()["received"] == 2 and r.json()["upserted"] == 1
    listed = ws.get(f"{API}/metrics").json()
    assert len(listed) == 1 and float(listed[0]["spend"]) == 20


def test_idempotency_key_replays_response(ws, raw_sql):
    c = make_campaign(ws, "amazon")
    rows = metric_rows(c["id"], 7, 50, 2.0)
    r1 = ws.bulk(rows, key="job-42")
    assert r1.headers["Idempotent-Replayed"] == "false"
    raw_sql("UPDATE {p}daily_metrics SET spend = 0")  # prove the replay does not re-run the write
    r2 = ws.bulk(rows, key="job-42")
    assert r2.status_code == 200
    assert r2.headers["Idempotent-Replayed"] == "true"
    assert r2.json()["idempotent_replay"] is True and r2.json()["upserted"] == 7
    [(total,)] = raw_sql("SELECT SUM(spend) FROM {p}daily_metrics")
    assert float(total) == 0


def test_idempotency_key_with_different_payload_rejected(ws):
    c = make_campaign(ws, "amazon")
    ws.bulk(metric_rows(c["id"], 3, 50, 2.0), key="k1")
    r = ws.bulk(metric_rows(c["id"], 3, 99, 2.0), key="k1")
    assert r.status_code == 422 and "Idempotency-Key" in r.json()["detail"]


def test_idempotency_keys_are_scoped_per_workspace(ws, other_ws):
    a = make_campaign(ws, "google")
    b = make_campaign(other_ws, "google")
    assert ws.bulk(metric_rows(a["id"], 2, 10, 1.0), key="nightly").status_code == 200
    r = other_ws.bulk(metric_rows(b["id"], 2, 10, 1.0), key="nightly")  # same key, other tenant: not a replay
    assert r.status_code == 200 and r.json()["idempotent_replay"] is False


def test_bulk_rejects_foreign_campaign(ws, other_ws):
    c = make_campaign(ws, "google")
    r = other_ws.bulk(metric_rows(c["id"], 2, 10, 1.0))
    assert r.status_code == 422 and "not in workspace" in r.json()["detail"]
    assert ws.get(f"{API}/metrics").json() == []


def test_bulk_validation_errors(ws):
    assert ws.bulk([]).status_code == 422
    c = make_campaign(ws, "google")
    assert ws.bulk([{"campaign_id": c["id"], "day": "2024-01-01", "spend": -5}]).status_code == 422
    assert ws.bulk([{"campaign_id": c["id"], "day": "not-a-date"}]).status_code == 422


def test_bulk_large_batch_spans_chunks(ws):
    c = make_campaign(ws, "google")
    r = ws.bulk(metric_rows(c["id"], 2500, 10, 2.0))  # > CHUNK size
    assert r.status_code == 200 and r.json()["upserted"] == 2500


def test_bulk_invalidates_report_cache(seeded):
    ws = seeded["ws"]
    ws.get(f"{API}/reports/by-channel")
    assert ws.get(f"{API}/reports/by-channel").headers["X-Cache"] == "HIT"
    ws.bulk(seeded["rows"][:1])
    assert ws.get(f"{API}/reports/by-channel").headers["X-Cache"] == "MISS"


def test_bulk_records_import_and_event(ws):
    c = make_campaign(ws, "google")
    r = ws.bulk(metric_rows(c["id"], 3, 10, 2.0))
    imp = ws.get(f"{API}/imports/{r.json()['import_id']}").json()
    assert imp["source"] == "api" and imp["rows_upserted"] == 3 and imp["status"] == "completed"
    evs = ws.get(f"{API}/events", params={"after": 0}).json()
    up = [e for e in evs if e["type"] == "metrics.upserted"]
    assert len(up) == 1 and up[0]["payload"]["rows"] == 3 and up[0]["payload"]["import_id"] == imp["id"]


def test_list_metrics_isolated_and_filterable(ws, other_ws):
    c = make_campaign(ws, "meta")
    ws.bulk(metric_rows(c["id"], 10, 10, 2.0, end=date(2024, 6, 30)))
    assert other_ws.get(f"{API}/metrics").json() == []
    r = ws.get(f"{API}/metrics", params={"start": "2024-06-28", "end": "2024-06-30"})
    assert [m["day"] for m in r.json()] == ["2024-06-30", "2024-06-29", "2024-06-28"]


def test_delete_metrics_for_campaign(ws, other_ws):
    c = make_campaign(ws, "meta")
    ws.bulk(metric_rows(c["id"], 4, 10, 2.0))
    assert other_ws.delete(f"{API}/metrics", params={"campaign_id": c["id"]}).status_code == 404
    assert ws.delete(f"{API}/metrics", params={"campaign_id": c["id"]}).status_code == 204
    assert ws.get(f"{API}/metrics").json() == []
