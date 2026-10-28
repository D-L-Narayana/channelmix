from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models import Channel


# ---------- accounts ----------
class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    currency: str = Field(default="USD", min_length=3, max_length=3)


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    currency: str
    created_at: datetime


# ---------- campaigns ----------
class CampaignCreate(BaseModel):
    channel: Channel
    external_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    status: str = "active"
    daily_budget: Decimal = Field(default=Decimal("0"), ge=0)


class CampaignUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    daily_budget: Decimal | None = Field(default=None, ge=0)


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    account_id: int
    channel: Channel
    external_id: str
    name: str
    status: str
    daily_budget: Decimal
    created_at: datetime


# ---------- metrics ----------
class MetricIn(BaseModel):
    campaign_id: int
    day: date
    impressions: int = Field(default=0, ge=0)
    clicks: int = Field(default=0, ge=0)
    conversions: int = Field(default=0, ge=0)
    spend: Decimal = Field(default=Decimal("0"), ge=0)
    revenue: Decimal = Field(default=Decimal("0"), ge=0)


class MetricOut(MetricIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    updated_at: datetime


class BulkMetricsRequest(BaseModel):
    rows: list[MetricIn] = Field(min_length=1, max_length=100_000)


class BulkMetricsResponse(BaseModel):
    received: int
    upserted: int
    campaigns_touched: int
    idempotent_replay: bool = False


# ---------- reports ----------
class ChannelMixRow(BaseModel):
    channel: Channel
    spend: float
    revenue: float
    impressions: int
    clicks: int
    conversions: int
    spend_share: float
    revenue_share: float
    roas: float | None
    cpa: float | None
    ctr: float | None
    cpc: float | None
    roas_rank: int


class ChannelMixReport(BaseModel):
    account_id: int
    start: date
    end: date
    total_spend: float
    total_revenue: float
    blended_roas: float | None
    channels: list[ChannelMixRow]


class TrendPoint(BaseModel):
    day: date
    channel: str
    spend: float
    revenue: float
    conversions: int
    roas: float | None
    spend_7d_avg: float
    roas_7d: float | None
    spend_dod_change: float | None
    cumulative_spend: float


class TrendReport(BaseModel):
    account_id: int
    start: date
    end: date
    group_by: str
    points: list[TrendPoint]


class CampaignPerformanceRow(BaseModel):
    campaign_id: int
    name: str
    channel: Channel
    status: str
    spend: float
    revenue: float
    impressions: int
    clicks: int
    conversions: int
    roas: float | None
    cpa: float | None
    spend_share_in_channel: float
    roas_rank_in_channel: int


# ---------- recommendations ----------
class RecommendationRequest(BaseModel):
    total_budget: Decimal | None = Field(default=None, gt=0, description="Daily budget to allocate")
    lookback_days: int = Field(default=30, ge=7, le=365)
    min_share: float = Field(default=0.05, ge=0, lt=0.5, description="Floor share per channel")
    max_shift_pct: float | None = Field(default=None, ge=0, le=1, description="Cap on |delta|/current")


class CurveFit(BaseModel):
    a: float
    b: float
    r2: float | None
    n_points: int
    method: str


class ChannelRecommendation(BaseModel):
    channel: Channel
    current_daily_spend: float
    recommended_daily_spend: float
    delta: float
    delta_pct: float | None
    current_roas: float | None
    marginal_roas_at_current: float | None
    marginal_roas_at_recommended: float | None
    projected_daily_revenue: float
    curve: CurveFit
    explanation: str


class RecommendationResponse(BaseModel):
    account_id: int
    total_budget: float
    lookback_days: int
    window_start: date
    window_end: date
    current_projected_revenue: float
    recommended_projected_revenue: float
    projected_uplift: float
    projected_uplift_pct: float | None
    channels: list[ChannelRecommendation]
    summary: str
    method: str
