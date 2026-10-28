<script setup lang="ts">
/**
 * Six KPI tiles: Spend, Impressions, Clicks, Conversions, CPA, ROAS — each with a delta
 * against the previous window of equal length (WoW for the 7-day preset). Delta uses
 * arrow + sign + % (never color alone); for CPA lower is better.
 */
import { computed } from 'vue'
import type { SummaryReport } from '../lib/types'
import { compact, daysBetween, money, num, pct, roas as fmtRoas } from '../lib/format'
import Skeleton from './ui/Skeleton.vue'

const props = defineProps<{ report: SummaryReport | null; loading?: boolean; currency: string }>()

interface Kpi {
  key: string
  label: string
  value: string
  full: string
  delta: number | null
  betterWhenLower?: boolean
}

const windowLabel = computed(() => {
  if (!props.report) return ''
  const d = daysBetween(props.report.start, props.report.end)
  return d === 7 ? 'WoW' : `vs prev. ${d}d`
})

const kpis = computed<Kpi[]>(() => {
  const r = props.report
  if (!r) return []
  const dp = r.delta_pct ?? {}
  const c = props.currency
  return [
    { key: 'spend', label: 'Spend', value: compact(r.spend, c), full: money(r.spend, c, 2), delta: dp.spend ?? null },
    { key: 'impressions', label: 'Impressions', value: compact(r.impressions), full: num(r.impressions), delta: dp.impressions ?? null },
    { key: 'clicks', label: 'Clicks', value: compact(r.clicks), full: num(r.clicks), delta: dp.clicks ?? null },
    { key: 'conversions', label: 'Conversions', value: compact(r.conversions), full: num(r.conversions), delta: dp.conversions ?? null },
    { key: 'cpa', label: 'CPA', value: r.cpa === null ? '–' : money(r.cpa, c, r.cpa < 100 ? 2 : 0), full: money(r.cpa, c, 2), delta: dp.cpa ?? null, betterWhenLower: true },
    { key: 'roas', label: 'ROAS', value: fmtRoas(r.roas), full: `${fmtRoas(r.roas)} (${money(r.revenue, c, 0)} revenue)`, delta: dp.roas ?? null },
  ]
})

function tone(k: Kpi): 'up' | 'down' | 'flat' | 'none' {
  if (k.delta === null || k.delta === undefined) return 'none'
  if (Math.abs(k.delta) < 0.0005) return 'flat'
  const good = k.betterWhenLower ? k.delta < 0 : k.delta > 0
  return good ? 'up' : 'down'
}
const arrow = (d: number | null) => (d === null ? '' : Math.abs(d) < 0.0005 ? '→' : d > 0 ? '↑' : '↓')
</script>

<template>
  <section class="kpis" aria-label="Key metrics" data-testid="kpis">
    <template v-if="loading || !report">
      <div v-for="i in 6" :key="i" class="tile" aria-busy="true">
        <Skeleton width="64px" height="12px" />
        <Skeleton width="110px" height="28px" />
        <Skeleton width="84px" height="12px" />
      </div>
    </template>
    <div v-else v-for="k in kpis" :key="k.key" class="tile" :data-testid="`kpi-${k.key}`">
      <div class="label">{{ k.label }}</div>
      <div class="value num" :title="k.full">{{ k.value }}</div>
      <div class="delta num" :class="tone(k)">
        <template v-if="k.delta !== null">
          <span class="arrow" aria-hidden="true">{{ arrow(k.delta) }}</span>
          <span>{{ pct(k.delta, 1, true) }}</span>
          <span class="muted win"> {{ windowLabel }}</span>
          <span class="sr-only">{{ tone(k) === 'up' ? 'improved' : tone(k) === 'down' ? 'worsened' : 'unchanged' }}</span>
        </template>
        <span v-else class="muted">no prior data</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.kpis { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; }
.tile { min-height: 104px; display: flex; flex-direction: column; justify-content: center; gap: 6px; padding: 16px 18px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg); box-shadow: var(--shadow-1); }
.label { font-size: var(--fs-12); font-weight: 500; letter-spacing: 0.04em; text-transform: uppercase; color: var(--muted); }
.value { font-size: var(--fs-28); font-weight: 500; letter-spacing: -0.02em; color: var(--text-strong); line-height: 1.1; font-variant-numeric: tabular-nums lining-nums; white-space: nowrap; }
.delta { font-size: var(--fs-12); display: flex; align-items: baseline; gap: 3px; color: var(--muted); white-space: nowrap; }
.delta .arrow { font-weight: 600; }
.delta.up { color: var(--success); }
.delta.down { color: var(--error); }
.delta.flat { color: var(--muted); }
.win { font-size: var(--fs-12); }
@media (max-width: 1200px) { .kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 640px) { .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; } .tile { padding: 12px 14px; min-height: 92px; } .value { font-size: var(--fs-24); } }
</style>
