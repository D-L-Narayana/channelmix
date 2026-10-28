"""SSE stream, polling fallback and the vendored sample dataset."""

import json
import threading
import time

from tests.conftest import API, make_campaign


def read_sse(ws, params=None, headers=None, max_seconds=5.0):
    """Consume the SSE stream until the server closes it; return parsed events (ready + typed) and comments."""
    events, comments = [], []
    cur: dict = {}
    with ws.client.stream("GET", f"{API}/stream", params=params or {}, headers={**ws.headers, **(headers or {})}) as r:
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("text/event-stream")
        for line in r.iter_lines():
            if line.startswith(":"):
                comments.append(line)
            elif line == "":
                if cur:
                    events.append(cur)
                cur = {}
            else:
                k, _, v = line.partition(":")
                cur[k] = v.strip()
    return events, comments


def test_stream_ready_heartbeat_and_close(ws, fast_sse):
    t0 = time.monotonic()
    events, comments = read_sse(ws)
    elapsed = time.monotonic() - t0
    assert events[0]["event"] == "ready" and events[0]["retry"] == "2000"
    ready = json.loads(events[0]["data"])
    assert ready["workspace_id"] == ws.id and ready["last_event_id"] == 0 and ready["max_seconds"] == 3.0
    assert any(c.startswith(": ping") for c in comments)  # heartbeat
    assert comments[-1].startswith(": reconnect") and elapsed < 6


def test_stream_emits_events_written_during_connection(ws, fast_sse):
    def writer():
        time.sleep(0.4)
        make_campaign(ws, "google")
        ws.bulk([{"channel": "meta", "external_id": "m1", "day": "2025-10-01", "spend": 5}])

    th = threading.Thread(target=writer)
    th.start()
    events, _ = read_sse(ws)
    th.join()
    typed = [(e["event"], json.loads(e["data"])) for e in events if e["event"] != "ready"]
    kinds = [k for k, _ in typed]
    assert kinds == ["campaign.changed", "campaign.changed", "metrics.upserted"], kinds
    ids = [int(e["id"]) for e in events[1:]]
    assert ids == sorted(ids) and all(d["id"] == i for (_, d), i in zip(typed, ids, strict=True))
    assert typed[-1][1]["payload"]["rows"] == 1


def test_stream_replays_from_last_event_id(ws, fast_sse):
    make_campaign(ws, "google")
    make_campaign(ws, "meta")
    # without a cursor: start at latest -> no history
    events, _ = read_sse(ws)
    assert [e["event"] for e in events] == ["ready"]
    # Last-Event-ID header (what EventSource sends on reconnect) replays everything after it
    events, _ = read_sse(ws, headers={"Last-Event-ID": "0"})
    assert [e["event"] for e in events] == ["ready", "campaign.changed", "campaign.changed"]
    events, _ = read_sse(ws, params={"last_event_id": events[1]["id"]})
    assert [e["event"] for e in events] == ["ready", "campaign.changed"]


def test_stream_is_scoped_to_workspace(ws, other_ws, fast_sse):
    make_campaign(other_ws, "google")
    events, _ = read_sse(ws, headers={"Last-Event-ID": "0"})
    assert [e["event"] for e in events] == ["ready"]
    assert ws.get(f"{API}/events", params={"after": 0}).json() == []
    assert len(other_ws.get(f"{API}/events", params={"after": 0}).json()) == 1


def test_events_polling_with_etag(ws):
    make_campaign(ws, "google")
    r = ws.get(f"{API}/events", params={"after": 0})
    assert r.status_code == 200 and len(r.json()) == 1
    etag = r.headers["ETag"]
    r2 = ws.get(f"{API}/events", params={"after": 0}, headers={"If-None-Match": etag})
    assert r2.status_code == 304
    make_campaign(ws, "meta")
    r3 = ws.get(f"{API}/events", params={"after": 0}, headers={"If-None-Match": etag})
    assert r3.status_code == 200 and len(r3.json()) == 2
    assert ws.get(f"{API}/events", params={"after": r3.json()[-1]["id"]}).json() == []


# ---------------- sample dataset ----------------
def test_sample_dataset_download_and_info(client):
    r = client.get(f"{API}/datasets/sample")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "kaggle.com" in r.headers["X-Dataset-Source"] and r.headers["X-Dataset-License"] == "MIT"
    header = r.text.splitlines()[0]
    assert header == "day,channel,campaign,external_id,impressions,clicks,conversions,spend,revenue"
    info = client.get(f"{API}/datasets/sample/info").json()
    assert info["license"] == "MIT" and info["rows"] == 1248 and info["campaigns"] == 18
    assert info["first_day"] == "2020-04-01" and info["last_day"] == "2020-06-30" and info["channels"] == ["other"]


def test_sample_dataset_import_is_real_data_and_idempotent(ws):
    r = ws.post(f"{API}/datasets/sample/import")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["status"] == "completed" and b["summary"]["rows_upserted"] == 1248
    assert b["summary"]["campaigns_created"] == 18 and b["summary"]["first_day"] == "2020-04-01"
    rep = ws.get(f"{API}/reports/summary", params={"start": "2020-04-01", "end": "2020-06-30"}).json()
    assert rep["days_with_data"] == 91 and rep["impressions"] == 239_017_725 and rep["clicks"] == 2_492_837
    imp = ws.get(f"{API}/imports").json()[0]
    assert imp["source"] == "sample"
    again = ws.post(f"{API}/datasets/sample/import").json()
    assert again["summary"]["campaigns_created"] == 0
    assert ws.get(f"{API}/workspaces/me").json()["stats"]["metric_rows"] == 1248
