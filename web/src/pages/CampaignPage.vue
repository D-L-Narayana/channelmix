<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import VChart from 'vue-echarts'
import '../lib/echarts'
import { animation, axisBase, chartText, tooltipBase } from '../lib/echarts'
import { useWorkspaceStore } from '../stores/workspace'
import { useToastStore } from '../stores/toast'
import { useQuery } from '../composables/useQuery'
import { useDateRange } from '../composables/useDateRange'
import { api, describeError } from '../lib/api'
import { displayCurrency, loadCurrency } from '../lib/currency'
import { channelLabel, compact, daysBetween, money, num, pct, roas as fmtRoas, seriesColor, shortDate } from '../lib/format'
import type { DailyMetric } from '../lib/types'
import Card from '../components/ui/Card.vue'
import Badge from '../components/ui/Badge.vue'
import Button from '../components/ui/Button.vue'
import Input from '../components/ui/Input.vue'
import Select from '../components/ui/Select.vue'
import Skeleton from '../components/ui/Skeleton.vue'
import EmptyState from '../components/ui/EmptyState.vue'
import Table, { type Column, type SortState } from '../components/ui/Table.vue'
import DateRangePicker from '../components/DateRangePicker.vue'
import ChartFrame from '../components/ChartFrame.vue'
import ErrorState from '../components/ErrorState.vue'

const ws = useWorkspaceStore()
const toast = useToastStore()
const route = useRoute()
const key = computed(() => ws.key as string)
const slug = computed(() => ws.slug as string)
const id = computed(() => String(route.params.id))
loadCurrency(slug.value)
const { range, preset, setPreset, set } = useDateRange(30)

const campaign = useQuery((s) => api.campaign(key.value, id.value, s), { refetchOn: ['campaign.changed'] })
const metrics = useQuery((s) => api.metrics(key.value, { campaign_id: id.value, start: range.value.start, end: range.value.end, limit: 5000 }, s), {
  deps: [range],
  refetchOn: ['metrics.upserted', 'import.completed'],
})

const rows = computed<DailyMetric[]>(() => [...(metrics.data.value ?? [])].map((m) => ({ ...m, spend: Number(m.spend), revenue: Number(m.revenue) })).sort((a, b) => (a.day < b.day ? -1 : 1)))
const totals = computed(() => {
  const t = { spend: 0, revenue: 0, impressions: 0, clicks: 0, conversions: 0 }
  for (const r of rows.value) {
    t.spend += Number(r.spend)
    t.revenue += Number(r.revenue)
    t.impressions += r.impressions
    t.clicks += r.clicks
    t.conversions += r.conversions
  }
  return { ...t, cpa: t.conversions ? t.spend / t.conversions : null, roas: t.spend ? t.revenue / t.spend : null, ctr: t.impressions ? t.clicks / t.impressions : null, cpc: t.clicks ? t.spend / t.clicks : null }
})
const days = computed(() => daysBetween(range.value.start, range.value.end))
const budget = computed(() => Number(campaign.data.value?.daily_budget ?? 0))
const pacing = computed(() => (budget.value > 0 && rows.value.length ? totals.value.spend / rows.value.length / budget.value : null))
const color = computed(() => seriesColor(campaign.data.value?.channel ?? 'other'))

const seriesFor = (field: 'spend' | 'conversions' | 'revenue' | 'clicks') => ({
  ...animation(),
  grid: { left: 8, right: 12, top: 10, bottom: 4, containLabel: true },
  tooltip: { ...tooltipBase, axisPointer: { type: 'shadow' }, valueFormatter: (v: number) => (field === 'spend' || field === 'revenue' ? money(v, displayCurrency.value, 2) : num(v)) },
  xAxis: { type: 'category', data: rows.value.map((r) => r.day), ...axisBase, axisLabel: { ...chartText, formatter: shortDate, hideOverlap: true } },
  yAxis: { type: 'value', ...axisBase, axisLabel: { ...chartText, formatter: (v: number) => compact(v, field === 'spend' || field === 'revenue' ? displayCurrency.value : undefined) }, min: 0 },
  series: [
    {
      name: field,
      type: 'bar',
      barMaxWidth: 18,
      itemStyle: { color: color.value, borderRadius: [2, 2, 0, 0] },
      data: rows.value.map((r) => Number(r[field])),
      markLine:
        field === 'spend' && budget.value > 0
          ? { silent: true, symbol: 'none', lineStyle: { color: '#8f8e8b', type: 'dashed' }, label: { ...chartText, formatter: 'budget' }, data: [{ yAxis: budget.value }] }
          : undefined,
    },
  ],
})
const spendOpt = computed(() => seriesFor('spend'))
const convOpt = computed(() => seriesFor('conversions'))

/* ---------- edit ---------- */
const editing = ref(false)
const fStatus = ref('active')
const fBudget = ref('')
const fName = ref('')
const saving = ref(false)
watch(
  () => campaign.data.value,
  (c) => {
    if (!c) return
    fStatus.value = c.status
    fBudget.value = String(c.daily_budget ?? '')
    fName.value = c.name
  },
  { immediate: true },
)
async function save() {
  saving.value = true
  try {
    await api.updateCampaign(key.value, id.value, { name: fName.value.trim(), status: fStatus.value, daily_budget: Number(fBudget.value) || 0 })
    toast.success('Campaign updated')
    editing.value = false
    await campaign.refetch()
  } catch (e) {
    toast.error('Could not save', describeError(e))
  } finally {
    saving.value = false
  }
}

/* ---------- daily table ---------- */
const sort = ref<SortState>({ key: 'day', dir: 'desc' })
const sorted = computed(() => {
  const { key: k, dir } = sort.value
  const sgn = dir === 'asc' ? 1 : -1
  return [...rows.value].sort((a, b) => {
    const av = a[k as keyof DailyMetric] as number | string
    const bv = b[k as keyof DailyMetric] as number | string
    return (typeof av === 'string' ? String(av).localeCompare(String(bv)) : Number(av) - Number(bv)) * sgn
  })
})
const columns: Column[] = [
  { key: 'day', label: 'Day', sortable: true, mono: true },
  { key: 'impressions', label: 'Impr.', align: 'right', sortable: true, hideBelow: 640 },
  { key: 'clicks', label: 'Clicks', align: 'right', sortable: true, hideBelow: 640 },
  { key: 'conversions', label: 'Conv.', align: 'right', sortable: true },
  { key: 'spend', label: 'Spend', align: 'right', sortable: true },
  { key: 'revenue', label: 'Revenue', align: 'right', sortable: true, hideBelow: 900 },
]
</script>

<template>
  <div class="page">
    <nav class="crumbs" aria-label="Breadcrumb">
      <router-link :to="`/w/${slug}`">Dashboard</router-link><span class="muted" aria-hidden="true"> / </span><span>Campaign</span>
    </nav>

    <Card v-if="campaign.error.value"><ErrorState :error="campaign.error.value" :retry="campaign.run" :title="campaign.error.value.kind === 'not_found' ? 'This campaign is not in your workspace' : undefined" /></Card>

    <template v-else>
      <header class="ph">
        <div class="ttl">
          <template v-if="campaign.data.value">
            <div class="row gap-2 wrap">
              <i class="sw" :style="{ background: color }" aria-hidden="true" />
              <h1 class="truncate">{{ campaign.data.value.name }}</h1>
              <Badge :tone="campaign.data.value.status === 'active' ? 'success' : campaign.data.value.status === 'paused' ? 'warning' : 'neutral'">{{ campaign.data.value.status }}</Badge>
            </div>
            <p class="muted sub">{{ channelLabel(campaign.data.value.channel) }} · <span class="mono">{{ campaign.data.value.external_id }}</span> · daily budget {{ budget > 0 ? money(budget, displayCurrency, 2) : 'not set' }} · id <span class="mono">{{ campaign.data.value.id }}</span></p>
          </template>
          <template v-else><Skeleton width="320px" height="26px" /><Skeleton width="240px" height="13px" /></template>
        </div>
        <div class="row gap-3 wrap">
          <Button size="sm" variant="secondary" :disabled="!campaign.data.value" @click="editing = !editing">{{ editing ? 'Close' : 'Edit' }}</Button>
          <DateRangePicker :model-value="range" :preset="preset" @update:model-value="set" @preset="setPreset" />
        </div>
      </header>

      <Card v-if="editing" title="Edit campaign">
        <form class="edit" @submit.prevent="save">
          <Input v-model="fName" label="Name" required />
          <Select v-model="fStatus" label="Status" :options="['active', 'paused', 'ended'].map((s) => ({ value: s, label: s }))" />
          <Input v-model="fBudget" type="number" min="0" step="0.01" inputmode="decimal" :label="`Daily budget (${displayCurrency})`" hint="Used for pacing. 0 = none." />
          <div class="row gap-2" style="align-self: end"><Button type="submit" variant="primary" :loading="saving">Save</Button></div>
        </form>
      </Card>

      <section class="stats" aria-label="Totals in range">
        <div v-for="s in [
            { l: 'Spend', v: money(totals.spend, displayCurrency) },
            { l: 'Impressions', v: compact(totals.impressions) },
            { l: 'Clicks', v: compact(totals.clicks), s: `CTR ${pct(totals.ctr, 2)}` },
            { l: 'Conversions', v: num(totals.conversions), s: `CPA ${money(totals.cpa, displayCurrency, 2)}` },
            { l: 'ROAS', v: fmtRoas(totals.roas), s: `${money(totals.revenue, displayCurrency)} revenue` },
            { l: 'Pacing', v: pacing === null ? '–' : pct(pacing, 0), s: pacing === null ? 'no budget set' : `${money(totals.spend / Math.max(1, rows.length), displayCurrency, 0)}/day of ${money(budget, displayCurrency, 0)}` },
          ]" :key="s.l" class="st">
          <div class="l">{{ s.l }}</div>
          <div v-if="metrics.loading.value" class="v"><Skeleton width="80px" height="24px" /></div>
          <div v-else class="v num">{{ s.v }}</div>
          <div class="s muted">{{ s.s ?? `${rows.length} of ${days} days` }}</div>
        </div>
      </section>

      <Card v-if="metrics.error.value"><ErrorState :error="metrics.error.value" :retry="metrics.run" /></Card>
      <template v-else>
        <div class="charts">
          <ChartFrame :title="budget > 0 && pacing !== null ? `Spending ${pct(pacing, 0)} of the daily budget on average` : 'Daily spend'" :loading="metrics.loading.value" :empty="!rows.length" :height="220" :desc="`Bar chart of daily spend for ${rows.length} days.`">
            <VChart class="chart" :option="spendOpt" autoresize />
            <template #table><table class="dt"><tbody><tr v-for="r in rows" :key="r.day"><td class="mono">{{ r.day }}</td><td class="num">{{ money(r.spend, displayCurrency, 2) }}</td></tr></tbody></table></template>
          </ChartFrame>
          <ChartFrame title="Daily conversions" :loading="metrics.loading.value" :empty="!rows.length" :height="220" :desc="`Bar chart of daily conversions for ${rows.length} days.`">
            <VChart class="chart" :option="convOpt" autoresize />
            <template #table><table class="dt"><tbody><tr v-for="r in rows" :key="r.day"><td class="mono">{{ r.day }}</td><td class="num">{{ num(r.conversions) }}</td></tr></tbody></table></template>
          </ChartFrame>
        </div>

        <Card title="Daily rows" :subtitle="`${rows.length} days with data in range`" flush>
          <Table :columns="columns" :rows="sorted" :row-key="(r) => r.day" v-model:sort="sort" :loading="metrics.loading.value" dense caption="Daily metrics for this campaign">
            <template #cell-impressions="{ value }">{{ num(value) }}</template>
            <template #cell-clicks="{ value }">{{ num(value) }}</template>
            <template #cell-conversions="{ value }">{{ num(value) }}</template>
            <template #cell-spend="{ value }">{{ money(value, displayCurrency, 2) }}</template>
            <template #cell-revenue="{ value }">{{ money(value, displayCurrency, 2) }}</template>
            <template #empty><EmptyState compact title="No rows in this range" body="Pick a wider range or import more days for this campaign." /></template>
          </Table>
        </Card>
      </template>
    </template>
  </div>
</template>

<style scoped>
.page { display: flex; flex-direction: column; gap: 18px; }
.crumbs { font-size: var(--fs-13); color: var(--muted); }
.crumbs a { color: var(--muted); }
.crumbs a:hover { color: var(--text-strong); }
.ph { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.ttl { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.ttl h1 { font-size: var(--fs-24); max-width: 60vw; }
.sw { width: 4px; height: 24px; border-radius: 2px; }
.sub { font-size: var(--fs-13); }
.edit { display: grid; grid-template-columns: 2fr 1fr 1fr auto; gap: 12px; align-items: start; }
.stats { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; }
.st { min-height: 92px; padding: 14px 16px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg); display: flex; flex-direction: column; gap: 4px; }
.l { font-size: var(--fs-12); text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); font-weight: 500; }
.v { font-size: var(--fs-24); color: var(--text-strong); font-weight: 500; letter-spacing: -0.02em; line-height: 1.1; }
.s { font-size: var(--fs-12); }
.charts { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.chart { width: 100%; height: 100%; }
.dt { width: 100%; border-collapse: collapse; font-size: var(--fs-13); }
.dt td { padding: 6px 10px; border-bottom: 1px solid var(--border); }
.dt .num { text-align: right; font-variant-numeric: tabular-nums; }
@media (max-width: 1100px) { .stats { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 900px) { .charts { grid-template-columns: 1fr; } .edit { grid-template-columns: 1fr 1fr; } }
@media (max-width: 640px) { .stats { grid-template-columns: repeat(2, 1fr); gap: 8px; } .ttl h1 { max-width: 100%; font-size: var(--fs-20); } .edit { grid-template-columns: 1fr; } }
</style>
