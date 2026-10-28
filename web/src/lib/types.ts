/** Types mirror api/CONTRACT.md (v1). Money is float in reports, decimal string in raw rows. */
export const CHANNELS = ['google', 'meta', 'amazon', 'linkedin', 'other'] as const
export type Channel = (typeof CHANNELS)[number]

export interface WorkspaceStats {
  campaigns: number
  metric_rows: number
  imports: number
  first_day: string | null
  last_day: string | null
}

export interface Workspace {
  id: number
  slug: string
  name: string
  email: string | null
  created_at: string
  stats?: WorkspaceStats
}

export interface WorkspaceCreated extends Workspace {
  api_key: string
}

export interface Campaign {
  id: number
  workspace_id?: number
  channel: Channel
  external_id: string
  name: string
  status: string
  daily_budget: string | number
  created_at?: string
  updated_at?: string
}

export interface DailyMetric {
  id?: number
  campaign_id: number
  day: string
  impressions: number
  clicks: number
  conversions: number
  spend: number | string
  revenue: number | string
  updated_at?: string
}

export interface MetricRowIn {
  campaign_id?: number
  channel?: Channel
  external_id?: string
  campaign_name?: string
  day: string
  impressions?: number
  clicks?: number
  conversions?: number
  spend?: number
  revenue?: number
}

export interface BulkResult {
  received: number
  upserted: number
  campaigns_touched: number
  campaigns_created: number
  idempotent_replay: boolean
  import_id: number | null
}

/* ---------- reports ---------- */
export interface SummaryMetrics {
  spend: number
  revenue: number
  impressions: number
  clicks: number
  conversions: number
  roas: number | null
  cpa: number | null
  ctr: number | null
  cpc: number | null
  days_with_data?: number
  campaigns?: number
}

export interface SummaryReport extends SummaryMetrics {
  start: string
  end: string
  previous: SummaryMetrics | null
  delta_pct: Partial<Record<keyof SummaryMetrics, number | null>>
}

export interface ChannelMixRow {
  channel: Channel
  spend: number
  revenue: number
  impressions: number
  clicks: number
  conversions: number
  spend_share: number
  revenue_share: number
  roas: number | null
  cpa: number | null
  ctr: number | null
  cpc: number | null
  roas_rank: number
}

export interface ChannelMixReport {
  start: string
  end: string
  total_spend: number
  total_revenue: number
  blended_roas: number | null
  channels: ChannelMixRow[]
}

export interface TrendPoint {
  day: string
  channel: Channel | 'all' | string
  spend: number
  revenue: number
  conversions: number
  roas: number | null
  spend_7d_avg: number
  roas_7d: number | null
  spend_dod_change: number | null
  cumulative_spend: number
}

export interface TrendReport {
  start: string
  end: string
  group_by: 'channel' | 'total'
  points: TrendPoint[]
}

export interface CampaignPerformanceRow {
  campaign_id: number
  name: string
  channel: Channel
  status: string
  spend: number
  revenue: number
  impressions: number
  clicks: number
  conversions: number
  roas: number | null
  cpa: number | null
  spend_share_in_channel: number
  roas_rank_in_channel: number
}

/* ---------- recommendations ---------- */
export interface CurveFit {
  a: number
  b: number
  r2: number | null
  n_points: number
  method: string
}

export interface ChannelRecommendation {
  channel: Channel
  current_daily_spend: number
  recommended_daily_spend: number
  delta: number
  delta_pct: number | null
  current_roas: number | null
  marginal_roas_at_current: number | null
  marginal_roas_at_recommended: number | null
  projected_daily_revenue: number
  curve: CurveFit
  explanation: string
}

export interface RecommendationResponse {
  total_budget: number
  lookback_days: number
  window_start: string
  window_end: string
  current_projected_revenue: number
  recommended_projected_revenue: number
  projected_uplift: number
  projected_uplift_pct: number | null
  channels: ChannelRecommendation[]
  summary: string
  method: string
}

export interface RecommendationRequest {
  total_budget?: number | null
  lookback_days?: number
  min_share?: number
  max_shift_pct?: number | null
}

export interface DateRange {
  start: string
  end: string
}

/* ---------- CSV import ---------- */
export type ImportFormat = 'google_ads' | 'meta_ads' | 'generic'
export type ImportStatus = 'dry_run' | 'completed' | 'failed'

export type MappingField = 'day' | 'campaign_name' | 'external_id' | 'impressions' | 'clicks' | 'conversions' | 'spend' | 'revenue' | 'channel'
/** our field -> source column (null = not present, defaults to 0) */
export type ColumnMapping = Record<MappingField, string | null>

export interface PreviewRow {
  day: string
  channel: Channel | string
  external_id: string
  campaign_name: string
  impressions: number
  clicks: number
  conversions: number
  spend: number
  revenue: number
}

export interface ImportSummary {
  rows_upserted: number
  campaigns_created: number
  campaigns_touched: number
  first_day: string | null
  last_day: string | null
}

export interface ImportResponse {
  import_id: number | null
  status: ImportStatus
  detected_format: ImportFormat
  confidence: number
  channel: Channel | string | null
  currency: string | null
  delimiter: string
  mapping: ColumnMapping
  source_columns: string[]
  unmapped_columns: string[]
  row_count: number
  skipped_rows: number
  preview: PreviewRow[]
  warnings: string[]
  summary: ImportSummary | null
  source?: string
}

export interface ImportRecord {
  id: number
  source: 'google_ads' | 'meta_ads' | 'generic' | 'api' | 'sample' | string
  filename: string | null
  status: ImportStatus | string
  rows_received: number
  rows_upserted: number
  campaigns_created: number
  warnings: string[]
  created_at: string
}

export interface SampleDatasetInfo {
  name: string
  source_url: string
  license: string
  attribution: string
  rows: number
  channels: string[]
  first_day: string | null
  last_day: string | null
  description: string
}

/* ---------- live ---------- */
export type LiveEventType = 'ready' | 'metrics.upserted' | 'campaign.changed' | 'import.completed' | 'message' | string

export interface LiveEvent {
  id: string | null
  type: LiveEventType
  data: Record<string, unknown>
  at: number
}

export interface StoredEvent {
  id: number
  type: LiveEventType
  created_at: string
  payload: Record<string, unknown>
}
