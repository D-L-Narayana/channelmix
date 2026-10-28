import json
import logging

from app.logging_middleware import REQUEST_LOGGER, configure_logging


def test_request_log_is_structured_json(client, ws, capsys):
    configure_logging("INFO")
    ws.get("/api/v1/workspaces/me", headers={"X-Request-ID": "req-1"})
    lines = [ln for ln in capsys.readouterr().out.splitlines() if '"request_id": "req-1"' in ln]
    assert lines, "no structured request log emitted"
    rec = json.loads(lines[-1])
    assert rec["request_id"] == "req-1"
    assert rec["workspace_id"] == ws.id
    assert rec["method"] == "GET" and rec["status"] == 200
    assert isinstance(rec["latency_ms"], (int, float)) and rec["latency_ms"] >= 0
    assert rec["service"] == "channelmix-api" and rec["path"] == "/api/v1/workspaces/me"
    assert "@timestamp" in rec and rec["level"] == "INFO"
    logging.getLogger().handlers = []


def test_request_log_without_workspace(client, caplog):
    with caplog.at_level(logging.INFO, logger=REQUEST_LOGGER):
        client.get("/health")
    recs = [r for r in caplog.records if r.name == REQUEST_LOGGER]
    assert recs and recs[-1].workspace_id is None and recs[-1].path == "/health"
