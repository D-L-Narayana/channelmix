"""Alembic environment. Uses DATABASE_URL (same setting as the app) and keeps everything in schema `channelmix`.

Run migrations against the Supabase *session* pooler (port 5432), not the transaction pooler.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import text

from app.config import get_settings
from app.db import SCHEMA, Base, make_engine
from app import models  # noqa: F401  (register tables)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
DB_URL = get_settings().database_url
IS_SQLITE = DB_URL.startswith("sqlite")


def include_object(obj, name, type_, reflected, compare_to):
    # never touch other apps' schemas in the shared database
    if type_ == "table" and obj.schema not in (SCHEMA, None):
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=DB_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=None if IS_SQLITE else SCHEMA,
        include_schemas=not IS_SQLITE,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = make_engine(DB_URL, pool="null")
    with engine.connect() as connection:
        if not IS_SQLITE:
            connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
            connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=None if IS_SQLITE else SCHEMA,
            include_schemas=not IS_SQLITE,
            include_object=include_object,
            render_as_batch=IS_SQLITE,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
