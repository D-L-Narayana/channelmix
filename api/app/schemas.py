from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models import Channel


# ---------- workspaces ----------
class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    name: str
    email: str
    created_at: datetime


class WorkspaceCreated(WorkspaceOut):
    api_key: str
    workspace_url: str


class WorkspaceStats(BaseModel):
    campaigns: int
    metric_rows: int
    imports: int
    first_day: date | None
    last_day: date | None


class WorkspaceMe(WorkspaceOut):
    stats: WorkspaceStats


# ---------- campaigns ----------
class CampaignCreate(BaseModel):
    channel: Channel
    external_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    status: str = Field(default="active", max_length=20)
    daily_budget: Decimal = Field(default=Decimal("0"), ge=0)


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: str | None = Field(default=None, max_length=20)
    daily_budget: Decimal | None = Field(default=None, ge=0)


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    workspace_id: int
    channel: Channel
    external_id: str
    name: str
    status: str
    daily_budget: Decimal
    created_at: datetime
    updated_at: datetime


# ---------- metrics ----------
class MetricIn(BaseModel):
    """Identify the campaign by ``campaign_id`` or by ``channel`` + ``external_id`` (auto-created)."""

    campaign_id: int | None = None
    channel: Channel | None = None
    external_id: str | None = Field(default=None, min_length=1, max_length=100)
    campaign_name: str | None = Field(default=None, max_length=200)
    day: date
    impressions: int = Field(default=0, ge=0)
    clicks: int = Field(default=0, ge=0)
    conversions: int = Field(default=0, ge=0)
    spend: Decimal = Field(default=Decimal("0"), ge=0)
    revenue: Decimal = Field(default=Decimal("0"), ge=0)

    @model_validator(mode="after")
    def _identity(self):
        if self.campaign_id is None and not (self.channel and self.external_id):
            raise ValueError("provide campaign_id or channel + external_id")
        return self


class MetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    campaign_id: int
    day: date
    impressions: int
    clicks: int
    conversions: int
    spend: Decimal
    revenue: Decimal
    updated_at: datetime


class BulkMetricsRequest(BaseModel):
    rows: list[MetricIn] = Field(min_length=1, max_length=100_000)


class BulkMetricsResponse(BaseModel):
    received: int
    upserted: int
    campaigns_touched: int
    campaigns_created: int = 0
    idempotent_replay: bool = False
    import_id: int | None = None


# ---------- imports ----------
class ImportSummary(BaseModel):
    rows_upserted: int
    campaigns_created: int
    campaigns_touched: int
    first_day: date | None
    last_day: date | None


class ImportPreviewRow(BaseModel):
    day: date
    channel: Channel
    external_id: str
    campaign_name: str
    impressions: int
    clicks: int
    conversions: int
    spend: float
    revenue: float


class ImportResult(BaseModel):
    import_id: int | None
    status: str
    detected_format: str
    confidence: float
    channel: Channel | None
    currency: str | None
    delimiter: str
    mapping: dict[str, str | None]
    source_columns: list[str]
    unmapped_columns: list[str]
    row_count: int
    skipped_rows: int
    preview: list[ImportPreviewRow]
    warnings: list[str]
    summary: ImportSummary | None


class ImportOut(BaseModel):
    id: int
    source: str
    filename: str | None
    status: str
    rows_received: int
    rows_upserted: int
    campaigns_created: int
    warnings: list[str]
    detail: dict[str, Any]
    created_at: datetime


# ---------- reports ----------
class SummaryTotals(BaseModel):
    spend: float
    revenue: float
    impressions: int
    clicks: int
    conversions: int
    roas: float | None
    cpa: float | None
    ctr: float | None
    cpc: float | None
    days_with_data: int
    campaigns: int


class SummaryReport(SummaryTotals):
    start: date
    end: date
    previous: SummaryTotals | None
    delta_pct: dict[str, float | None]


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
    end: date | None = None


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


# ---------- events ----------
class EventOut(BaseModel):
    id: int
    type: str
    created_at: datetime | None
    payload: dict[str, Any]


# ---------- datasets ----------
class DatasetInfo(BaseModel):
    name: str
    source_url: str
    license: str
    attribution: str
    description: str
    rows: int
    campaigns: int
    channels: list[str]
    first_day: date
    last_day: date
    currency: str
