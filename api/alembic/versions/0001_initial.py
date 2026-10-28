"""initial schema: workspaces, campaigns, daily_metrics, imports, events, idempotency_keys

Revision ID: 0001_initial
Revises:
Create Date: 2025-10-28

Everything lives in the PostgreSQL schema ``channelmix`` (created here if missing). On SQLite the schema
is dropped (no schema support) so the same migration can be exercised locally.
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _schema() -> str | None:
    return None if op.get_bind().dialect.name == "sqlite" else "channelmix"


def _ref(table: str) -> str:
    s = _schema()
    return f"{s}.{table}" if s else table


CHANNEL = sa.Enum("google", "meta", "amazon", "linkedin", "other", name="channel", native_enum=False, length=16)


def upgrade() -> None:
    s = _schema()
    if s:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {s}")

    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("api_key_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("slug", name="uq_workspaces_slug"),
        sa.UniqueConstraint("api_key_hash", name="uq_workspaces_api_key_hash"),
        schema=s,
    )
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey(_ref("workspaces.id"), ondelete="CASCADE"), nullable=False),
        sa.Column("channel", CHANNEL, nullable=False),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("daily_budget", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "channel", "external_id", name="uq_campaign_external"),
        schema=s,
    )
    op.create_index("ix_campaigns_workspace_channel", "campaigns", ["workspace_id", "channel"], schema=s)

    op.create_table(
        "daily_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey(_ref("campaigns.id"), ondelete="CASCADE"), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("impressions", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("clicks", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("conversions", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("spend", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("revenue", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("campaign_id", "day", name="uq_metric_campaign_day"),
        schema=s,
    )
    op.create_index("ix_daily_metrics_day", "daily_metrics", ["day"], schema=s)

    op.create_table(
        "imports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey(_ref("workspaces.id"), ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("filename", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("rows_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_upserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("campaigns_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warnings_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("detail_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=s,
    )
    op.create_index("ix_imports_workspace_created", "imports", ["workspace_id", "created_at"], schema=s)

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey(_ref("workspaces.id"), ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=s,
    )
    op.create_index("ix_events_workspace_id_id", "events", ["workspace_id", "id"], schema=s)

    op.create_table(
        "idempotency_keys",
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey(_ref("workspaces.id"), ondelete="CASCADE"), primary_key=True),
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=s,
    )


def downgrade() -> None:
    s = _schema()
    for t in ("idempotency_keys", "events", "imports", "daily_metrics", "campaigns", "workspaces"):
        op.drop_table(t, schema=s)
