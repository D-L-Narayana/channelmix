from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import init_db
from app.deps import get_cache
from app.logging_middleware import RequestLoggingMiddleware, configure_logging
from app.routers import accounts, campaigns, metrics, reports

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging(settings.log_level)
    init_db()
    get_cache()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="Unified cross-channel ad spend (Google, Meta, Amazon), reports and budget reallocation.",
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/api/v1/openapi.json",
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Cache", "X-Request-ID", "Idempotent-Replayed"],
    )
    for r in (accounts.router, campaigns.router, metrics.router, reports.router):
        app.include_router(r, prefix=settings.api_prefix)

    @app.get("/health", tags=["ops"])
    def health():
        return {"status": "ok", "cache": get_cache().backend, "version": app.version}

    return app


app = create_app()
