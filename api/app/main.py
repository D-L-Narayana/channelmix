from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import engine, init_db, is_sqlite
from app.deps import get_cache
from app.logging_middleware import RequestLoggingMiddleware, configure_logging
from app.routers import campaigns, datasets, imports, metrics, reports, stream, workspaces

settings = get_settings()
VERSION = "2.0.0"


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging(settings.log_level)
    # SQLite (tests / local quick start) is created on the fly; PostgreSQL is managed by Alembic migrations.
    if is_sqlite(settings.database_url):
        init_db()
    get_cache()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=VERSION,
        description=(
            "Multi-tenant cross-channel ad performance API: workspaces with API keys, CSV/REST ingestion "
            "(Google Ads, Meta Ads Manager, generic), SQL window-function reports, budget reallocation and a "
            "live SSE change feed."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/api/v1/openapi.json",
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_origin_regex=r"https://channelmix(-[a-z0-9-]+)?(-nvr0910-3257s-projects)?\.vercel\.app",
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Cache", "X-Request-ID", "Idempotent-Replayed", "ETag", "X-Dataset-Source"],
    )
    for r in (
        workspaces.router,
        campaigns.router,
        metrics.router,
        imports.router,
        reports.router,
        stream.router,
        datasets.router,
    ):
        app.include_router(r, prefix=settings.api_prefix)

    @app.get("/health", tags=["ops"])
    def health():
        return {
            "status": "ok",
            "version": app.version,
            "cache": get_cache().backend,
            "database": engine.dialect.name,
        }

    return app


app = create_app()
