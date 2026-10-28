import type { Campaign, CampaignPerformanceRow, ImportResponse, SummaryReport } from '../lib/types'

export const summary: SummaryReport = {
  start: '2025-10-22',
  end: '2025-10-28',
  spend: 12345.6,
  revenue: 45678.9,
  impressions: 100000,
  clicks: 2500,
  conversions: 120,
  roas: 3.7,
  cpa: 102.88,
  ctr: 0.025,
  cpc: 4.94,
  days_with_data: 7,
  campaigns: 6,
  previous: { spend: 11000, revenue: 47000, impressions: 90000, clicks: 2600, conversions: 125, roas: 4.27, cpa: 88, ctr: 0.029, cpc: 4.23 },
  delta_pct: { spend: 0.1223, revenue: -0.0281, impressions: 0.111, clicks: -0.0385, conversions: -0.04, roas: -0.1335, cpa: 0.169, ctr: null, cpc: 0.168 },
}

export const perfRows: CampaignPerformanceRow[] = [
  { campaign_id: 1, name: 'Brand search', channel: 'google', status: 'active', spend: 3000, revenue: 12000, impressions: 40000, clicks: 1200, conversions: 60, roas: 4, cpa: 50, spend_share_in_channel: 0.6, roas_rank_in_channel: 1 },
  { campaign_id: 2, name: 'Generic search', channel: 'google', status: 'active', spend: 2000, revenue: 4000, impressions: 30000, clicks: 700, conversions: 20, roas: 2, cpa: 100, spend_share_in_channel: 0.4, roas_rank_in_channel: 2 },
  { campaign_id: 3, name: 'Retargeting — cart', channel: 'meta', status: 'paused', spend: 1500, revenue: 6000, impressions: 20000, clicks: 400, conversions: 30, roas: 4, cpa: 50, spend_share_in_channel: 1, roas_rank_in_channel: 1 },
  { campaign_id: 4, name: 'Sponsored products', channel: 'amazon', status: 'active', spend: 900, revenue: 1800, impressions: 10000, clicks: 200, conversions: 10, roas: 2, cpa: 90, spend_share_in_channel: 1, roas_rank_in_channel: 1 },
]

export const campaigns: Campaign[] = [
  { id: 1, channel: 'google', external_id: 'g-1', name: 'Brand search', status: 'active', daily_budget: '500.00' },
  { id: 2, channel: 'google', external_id: 'g-2', name: 'Generic search', status: 'active', daily_budget: '100.00' },
  { id: 3, channel: 'meta', external_id: 'm-1', name: 'Retargeting — cart', status: 'paused', daily_budget: '0.00' },
  { id: 4, channel: 'amazon', external_id: 'a-1', name: 'Sponsored products', status: 'active', daily_budget: '300.00' },
]

export const preview: ImportResponse = {
  import_id: null,
  status: 'dry_run',
  detected_format: 'google_ads',
  confidence: 0.92,
  channel: 'google',
  currency: 'INR',
  delimiter: ',',
  mapping: { day: 'Day', campaign_name: 'Campaign', external_id: 'Campaign ID', impressions: 'Impressions', clicks: 'Clicks', conversions: 'Conversions', spend: 'Cost', revenue: null, channel: null },
  source_columns: ['Campaign', 'Campaign ID', 'Day', 'Cost', 'Impressions', 'Clicks', 'Conversions', 'Campaign status'],
  unmapped_columns: ['Campaign status'],
  row_count: 120,
  skipped_rows: 2,
  preview: [
    { day: '2025-10-01', channel: 'google', external_id: 'brand-search', campaign_name: 'Brand search', impressions: 1000, clicks: 50, conversions: 3, spend: 42.5, revenue: 0 },
    { day: '2025-10-02', channel: 'google', external_id: 'brand-search', campaign_name: 'Brand search', impressions: 1200, clicks: 55, conversions: 4, spend: 44.1, revenue: 0 },
  ],
  warnings: ['No revenue column detected; revenue set to 0', "Row 14: unparseable day 'n/a' — skipped"],
  summary: null,
}
