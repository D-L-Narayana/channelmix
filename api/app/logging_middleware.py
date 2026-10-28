"""Structured JSON request logging.

Every request emits one JSON line (stdout) with request_id, method, path, status, workspace_id (resolved
from the API key by the auth dependency) and latency_ms. Vercel / Logstash pick these lines up as-is.
"""

from __future__ import annotations

import logging
import sys
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

try:  # python-json-logger >= 3
    from pythonjsonlogger.json import JsonFormatter
except ImportError:  # pragma: no cover - older versions
    from pythonjsonlogger.jsonlogger import JsonFormatter  # type: ignore[no-redef]

REQUEST_LOGGER = "channelmix.request"


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter(
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
            self.log.info(
                "request",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "workspace_id": getattr(request.state, "workspace_id", None),
                    "latency_ms": latency_ms,
                    "client": request.client.host if request.client else None,
                    "service": "channelmix-api",
                },
            )
