<script setup lang="ts">
/**
 * Campaign table: sort by any numeric column, filter by channel / status / text,
 * pacing = average daily spend in the window vs the campaign's daily budget.
 */
import { computed, ref } from 'vue'
import type { Campaign, CampaignPerformanceRow, Channel } from '../lib/types'
import { channelLabel, money, num, pct, roas as fmtRoas, seriesColor } from '../lib/format'
import Table, { type Column, type SortState } from './ui/Table.vue'
import Badge from './ui/Badge.vue'
import Input from './ui/Input.vue'
import Select from './ui/Select.vue'

export interface CampaignRow extends CampaignPerformanceRow {
  external_id: string | null
  daily_budget: number | null
  avg_daily_spend: number
  pacing: number | null // avg daily spend / daily budget
}

const props = defineProps<{
  rows: CampaignPerformanceRow[]
  campaigns: Campaign[]
  days: number
  loading?: boolean
  currency: string
  channel?: Channel | null
}>()
const emit = defineEmits<{ open: [id: number]; 'update:channel': [c: Channel | null] }>()

const search = ref('')
const status = ref<string>('')
const sort = ref<SortState>({ key: 'spend', dir: 'desc' })

const merged = computed<CampaignRow[]>(() => {
  const byId = new Map(props.campaigns.map((c) => [c.id, c]))
  const days = Math.max(1, props.days)
  return props.rows.map((r) => {
    const c = byId.get(r.campaign_id)
    const budget = c ? Number(c.daily_budget) : null
    const avg = r.spend / days
    return {
      ...r,
      status: c?.status ?? r.status,
      external_id: c?.external_id ?? null,
      daily_budget: budget && budget > 0 ? budget : null,
      avg_daily_spend: avg,
      pacing: budget && budget > 0 ? avg / budget : null,
    }
  })
})

const statuses = computed(() => Array.from(new Set(merged.value.map((r) => r.status))).sort())
const channels = computed(() => Array.from(new Set(merged.value.map((r) => r.channel))).sort())

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  let out = merged.value
  if (props.channel) out = out.filter((r) => r.channel === props.channel)
  if (status.value) out = out.filter((r) => r.status === status.value)
  if (q) out = out.filter((r) => r.name.toLowerCase().includes(q) || (r.external_id ?? '').toLowerCase().includes(q))
  const { key, dir } = sort.value
  const sgn = dir === 'asc' ? 1 : -1
  return [...out].sort((a, b) => {
    const av = a[key as keyof CampaignRow] as number | string | null
    const bv = b[key as keyof CampaignRow] as number | string | null
    if (av === null || av === undefined) return 1
    if (bv === null || bv === undefined) return -1
    if (typeof av === 'string' || typeof bv === 'string') return String(av).localeCompare(String(bv)) * sgn
    return (av - bv) * sgn
  })
})

const totals = computed(() => {
  const t = { spend: 0, revenue: 0, impressions: 0, clicks: 0, conversions: 0 }
  for (const r of filtered.value) {
    t.spend += r.spend
    t.revenue += r.revenue
    t.impressions += r.impressions
    t.clicks += r.clicks
    t.conversions += r.conversions
  }
  return { ...t, cpa: t.conversions ? t.spend / t.conversions : null, roas: t.spend ? t.revenue / t.spend : null }
})

const columns: Column[] = [
  { key: 'name', label: 'Campaign', sortable: true },
  { key: 'status', label: 'Status', hideBelow: 900 },
  { key: 'spend', label: 'Spend', align: 'right', sortable: true },
  { key: 'impressions', label: 'Impr.', align: 'right', sortable: true, hideBelow: 1100 },
  { key: 'clicks', label: 'Clicks', align: 'right', sortable: true, hideBelow: 1100 },
  { key: 'conversions', label: 'Conv.', align: 'right', sortable: true, hideBelow: 640 },
  { key: 'cpa', label: 'CPA', align: 'right', sortable: true, hideBelow: 900 },
  { key: 'roas', label: 'ROAS', align: 'right', sortable: true },
  { key: 'pacing', label: 'Pacing', align: 'right', sortable: true, hideBelow: 640, width: '150px' },
]

const statusTone = (s: string) => (s === 'active' || s === 'enabled' ? 'success' : s === 'paused' ? 'warning' : s === 'removed' || s === 'ended' ? 'neutral' : 'info')
const pacingTone = (p: number | null) => (p === null ? 'none' : p > 1.1 ? 'over' : p < 0.6 ? 'under' : 'ok')
</script>

<template>
  <div class="ct">
    <div class="toolbar">
      <div class="chips" role="group" aria-label="Filter by channel">
        <button type="button" class="chip" :class="{ on: !channel }" :aria-pressed="!channel" @click="emit('update:channel', null)">All</button>
        <button v-for="(c, i) in channels" :key="c" type="button" class="chip" :class="{ on: channel === c }" :aria-pressed="channel === c" :data-testid="`filter-${c}`" @click="emit('update:channel', channel === c ? null : c)">
          <i :style="{ background: seriesColor(c, i) }" aria-hidden="true" />{{ channelLabel(c) }}
        </button>
      </div>
      <div class="grow" />
      <Select v-model="status" size="sm" aria-label="Filter by status" :options="[{ value: '', label: 'Any status' }, ...statuses.map((s) => ({ value: s, label: s }))]" />
      <Input v-model="search" size="sm" type="search" placeholder="Search campaigns" aria-label="Search campaigns" data-testid="search" />
    </div>

    <Table
      :columns="columns"
      :rows="filtered"
      :row-key="(r) => r.campaign_id"
      v-model:sort="sort"
      :loading="loading"
      :skeleton-rows="6"
      caption="Campaign performance in the selected date range"
      clickable
      @row-click="(r) => emit('open', r.campaign_id)"
    >
      <template #cell-name="{ row }">
        <div class="namecell" data-testid="campaign-row">
          <i class="swatch" :style="{ background: seriesColor(row.channel, channels.indexOf(row.channel)) }" :title="channelLabel(row.channel)" aria-hidden="true" />
          <div class="nm">
            <span class="truncate n">{{ row.name }}</span>
            <span class="sub"><span>{{ channelLabel(row.channel) }}</span><span v-if="row.external_id" class="mono"> · {{ row.external_id }}</span></span>
          </div>
        </div>
      </template>
      <template #cell-status="{ value }"><Badge :tone="statusTone(value)" size="sm">{{ value }}</Badge></template>
      <template #cell-spend="{ value }">{{ money(value, currency) }}</template>
      <template #cell-impressions="{ value }">{{ num(value) }}</template>
      <template #cell-clicks="{ value }">{{ num(value) }}</template>
      <template #cell-conversions="{ value }">{{ num(value) }}</template>
      <template #cell-cpa="{ value }">{{ money(value, currency, 2) }}</template>
      <template #cell-roas="{ value }">{{ fmtRoas(value) }}</template>
      <template #cell-pacing="{ row }">
        <div v-if="row.pacing !== null" class="pace" :class="pacingTone(row.pacing)" :title="`${money(row.avg_daily_spend, currency, 2)}/day of ${money(row.daily_budget, currency, 2)} budget`">
          <span class="bar" aria-hidden="true"><span :style="{ width: Math.min(100, row.pacing * 100) + '%' }" /></span>
          <span class="num pv">{{ pct(row.pacing, 0) }}</span>
        </div>
        <span v-else class="muted" title="No daily budget set">–</span>
      </template>
      <template #empty>
        <span class="muted">No campaigns match these filters.</span>
      </template>
      <template #foot>
        <tr>
          <td>Total <span class="muted">({{ filtered.length }})</span></td>
          <td class="hide-900"></td>
          <td class="num right">{{ money(totals.spend, currency) }}</td>
          <td class="num right hide-1100">{{ num(totals.impressions) }}</td>
          <td class="num right hide-1100">{{ num(totals.clicks) }}</td>
          <td class="num right hide-640">{{ num(totals.conversions) }}</td>
          <td class="num right hide-900">{{ money(totals.cpa, currency, 2) }}</td>
          <td class="num right">{{ fmtRoas(totals.roas) }}</td>
          <td class="hide-640"></td>
        </tr>
      </template>
    </Table>
  </div>
</template>

<style scoped>
.ct { display: flex; flex-direction: column; }
.toolbar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 0 20px 14px; }
.chips { display: flex; gap: 4px; flex-wrap: wrap; }
.chip { display: inline-flex; align-items: center; gap: 6px; height: 30px; padding: 0 10px; border-radius: var(--r-pill); border: 1px solid var(--border); background: var(--surface-2); color: var(--muted); font-size: var(--fs-13); font-weight: 500; }
.chip i { width: 8px; height: 8px; border-radius: 2px; }
.chip:hover { color: var(--text-strong); border-color: var(--border-strong); }
.chip.on { color: var(--text-strong); background: var(--surface-3); border-color: var(--border-strong); }
.namecell { display: flex; align-items: center; gap: 10px; min-width: 0; max-width: 360px; }
.swatch { width: 3px; height: 28px; border-radius: 2px; flex-shrink: 0; }
.nm { display: flex; flex-direction: column; min-width: 0; line-height: 1.3; }
.n { color: var(--text-strong); font-weight: 500; }
.sub { font-size: var(--fs-12); color: var(--muted); }
.pace { display: inline-flex; align-items: center; gap: 8px; justify-content: flex-end; }
.bar { width: 64px; height: 4px; border-radius: 2px; background: var(--surface-3); overflow: hidden; display: inline-block; }
.bar span { display: block; height: 100%; background: var(--muted); border-radius: 2px; }
.pace.ok .bar span { background: var(--success); }
.pace.over .bar span { background: var(--warning-text); }
.pace.under .bar span { background: var(--info); }
.pv { min-width: 36px; text-align: right; font-size: var(--fs-13); }
.right { text-align: right; }
@media (max-width: 1100px) { .hide-1100 { display: none; } }
@media (max-width: 900px) { .hide-900 { display: none; } }
@media (max-width: 640px) { .hide-640 { display: none; } .toolbar { padding: 0 14px 12px; } .namecell { max-width: 200px; } }
</style>
