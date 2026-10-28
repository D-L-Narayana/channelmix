"""Structured JSON request logging.

Every request emits one JSON line (stdout) with request_id, method, path,
status, account_id (parsed from the route) and latency_ms. Logstash picks
these lines up (see elk/logstash.conf) and ships them to Elasticsearch.
"""

from __future__ import annotations

import logging
import re
import sys
import time
import uuid

from pythonjsonlogger import jsonlogger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

ACCOUNT_RE = re.compile(r"/accounts/(\d+)")
REQUEST_LOGGER = "channelmix.request"


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "@timestamp", "levelname": "level", "name": "logger"},
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, logger: logging.Logger | None = None):
        super().__init__(app)
        self.log = logger or logging.getLogger(REQUEST_LOGGER)

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            m = ACCOUNT_RE.search(request.url.path)
            account_id = int(m.group(1)) if m else None
            if account_id is None and request.query_params.get("account_id", "").isdigit():
                account_id = int(request.query_params["account_id"])
            self.log.info(
                "request",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "account_id": account_id,
                    "latency_ms": latency_ms,
                    "client": request.client.host if request.client else None,
                    "service": "channelmix-api",
                },
            )
