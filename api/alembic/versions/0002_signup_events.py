"""signup_events throttle table

Revision ID: 0002_signup_events
Revises: 0001_initial
"""

import sqlalchemy as sa

from alembic import op
from app.db import SCHEMA


def _schema() -> str | None:
    return None if op.get_bind().dialect.name == "sqlite" else SCHEMA


revision = "0002_signup_events"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    s = _schema()
    op.create_table(
        "signup_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ip_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=s,
    )
    op.create_index("ix_signup_events_ip_hash", "signup_events", ["ip_hash"], schema=s)
    op.create_index("ix_signup_events_created_at", "signup_events", ["created_at"], schema=s)


def downgrade() -> None:
    op.drop_table("signup_events", schema=_schema())
