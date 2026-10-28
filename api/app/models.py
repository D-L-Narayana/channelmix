import enum
from datetime import date, datetime, timezone

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Channel(str, enum.Enum):
    google = "google"
    meta = "meta"
    amazon = "amazon"
    linkedin = "linkedin"
    other = "other"


CHANNELS = [c.value for c in Channel]


class Workspace(Base):
    """A tenant. Everything else hangs off a workspace and is only reachable with its API key."""

    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")


class Campaign(Base):
    """Unified campaign model: the same shape regardless of channel."""

    __tablename__ = "campaigns"
    __table_args__ = (
        UniqueConstraint("workspace_id", "channel", "external_id", name="uq_campaign_external"),
        Index("ix_campaigns_workspace_channel", "workspace_id", "channel"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    channel: Mapped[Channel] = mapped_column(
        Enum(Channel, name="channel", native_enum=False, length=16, validate_strings=True), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    daily_budget: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    workspace: Mapped[Workspace] = relationship(back_populates="campaigns")
    metrics: Mapped[list["DailyMetric"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", passive_deletes=True
    )


class DailyMetric(Base):
    """One row per campaign per day. Natural key (campaign_id, day) drives the upsert."""

    __tablename__ = "daily_metrics"
    __table_args__ = (
        UniqueConstraint("campaign_id", "day", name="uq_metric_campaign_day"),
        Index("ix_daily_metrics_day", "day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    impressions: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    clicks: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    conversions: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    spend: Mapped[float] = mapped_column(Numeric(14, 4), default=0, nullable=False)
    revenue: Mapped[float] = mapped_column(Numeric(14, 4), default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    campaign: Mapped[Campaign] = relationship(back_populates="metrics")


class Import(Base):
    """Audit record of every ingest (CSV upload, bulk API call, sample dataset)."""

    __tablename__ = "imports"
    __table_args__ = (Index("ix_imports_workspace_created", "workspace_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # google_ads|meta_ads|generic|api|sample
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # completed|failed
    rows_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_upserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    campaigns_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warnings_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    detail_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)  # mapping / summary
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Event(Base):
    """Append-only change feed consumed by GET /stream (SSE) and GET /events."""

    __tablename__ = "events"
    __table_args__ = (Index("ix_events_workspace_id_id", "workspace_id", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class IdempotencyKey(Base):
    """Stores the response of a completed bulk request so retries are replayed, not re-applied."""

    __tablename__ = "idempotency_keys"

    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True, nullable=False
    )
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
