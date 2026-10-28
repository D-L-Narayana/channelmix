export type Channel = 'google' | 'meta' | 'amazon'

export interface Account {
  id: number
  name: string
  currency: string
  created_at: string
}

export interface Campaign {
  id: number
  account_id: number
  channel: Channel
  external_id: string
  name: string
  status: string
  daily_budget: string | number
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
  account_id: number
  start: string
  end: string
  total_spend: number
  total_revenue: number
  blended_roas: number | null
  channels: ChannelMixRow[]
}

export interface TrendPoint {
  day: string
  channel: string
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
  account_id: number
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
  account_id: number
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
  total_budget?: number
  lookback_days?: number
  min_share?: number
  max_shift_pct?: number | null
}

export interface DateRange {
  start: string
  end: string
}
