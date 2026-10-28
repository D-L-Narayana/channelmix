"""Engine / session factory.

All tables live in the PostgreSQL schema ``channelmix`` (shared Supabase project, one schema per app).
SQLite has no schemas, so the SQLite engine carries a ``schema_translate_map`` that strips the schema
at compile time; the same models/queries run unchanged in tests and local dev.
"""

from collections.abc import Generator

from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from app.config import get_settings

SCHEMA = "channelmix"

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA, naming_convention=NAMING)


def is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def table_prefix(bind) -> str:
    """Schema prefix for hand-written SQL: 'channelmix.' on PostgreSQL, '' on SQLite."""
    return "" if bind.dialect.name == "sqlite" else f"{SCHEMA}."


def make_engine(url: str, pool: str | None = None) -> Engine:
    """Create an engine for PostgreSQL (psycopg 3) or SQLite (tests / local dev)."""
    if is_sqlite(url):
        kwargs: dict = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url or url.endswith("sqlite://"):
            kwargs["poolclass"] = StaticPool
        base = create_engine(url, **kwargs)

        @event.listens_for(base, "connect")
        def _sqlite_pragmas(dbapi_conn, _):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        return base.execution_options(schema_translate_map={SCHEMA: None})

    pool = pool or get_settings().db_pool
    kwargs = {
        "pool_pre_ping": True,
        # Transaction-mode poolers (Supabase 6543) do not support server-side prepared statements.
        "connect_args": {"prepare_threshold": None},
    }
    if pool == "null":
        kwargs["poolclass"] = NullPool
    else:
        kwargs.update(pool_size=5, max_overflow=10, pool_recycle=1800)
    return create_engine(url, **kwargs)


engine: Engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_sessionmaker() -> sessionmaker:
    """Dependency returning the session factory (overridden in tests). Used by long-lived handlers (SSE)."""
    return SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(target: Engine | None = None) -> None:
    """Create tables (SQLite / tests). PostgreSQL deployments use Alembic migrations instead."""
    from app import models  # noqa: F401  (register tables)

    eng = target or engine
    if eng.dialect.name == "postgresql":
        from sqlalchemy import text

        with eng.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
    Base.metadata.create_all(bind=eng)
