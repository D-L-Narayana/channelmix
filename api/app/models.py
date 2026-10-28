import enum
from datetime import date, datetime, timezone

from sqlalchemy import (
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


class Account(Base):
    """An advertiser account that owns campaigns across one or more channels."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="account", cascade="all, delete-orphan")


class Campaign(Base):
    """Unified campaign model: the same shape regardless of channel."""

    __tablename__ = "campaigns"
    __table_args__ = (
        UniqueConstraint("account_id", "channel", "external_id", name="uq_campaign_external"),
        Index("ix_campaigns_account_channel", "account_id", "channel"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    channel: Mapped[Channel] = mapped_column(
        Enum(Channel, name="channel", native_enum=False, length=16), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    daily_budget: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    account: Mapped[Account] = relationship(back_populates="campaigns")
    metrics: Mapped[list["DailyMetric"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")


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
    impressions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    conversions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    spend: Mapped[float] = mapped_column(Numeric(14, 4), default=0, nullable=False)
    revenue: Mapped[float] = mapped_column(Numeric(14, 4), default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    campaign: Mapped[Campaign] = relationship(back_populates="metrics")


class IdempotencyKey(Base):
    """Stores the response of a completed bulk request so retries are replayed, not re-applied."""

    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    account_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
