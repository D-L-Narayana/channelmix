<script setup lang="ts">
/** Daily trend per channel (line). Metric switch: spend / revenue / conversions / ROAS. */
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import '../lib/echarts'
import { animation, axisBase, chartText, tooltipBase } from '../lib/echarts'
import type { Channel, TrendReport } from '../lib/types'
import { channelLabel, compact, money, num, pct, roas as fmtRoas, seriesColor, shortDate } from '../lib/format'
import ChartFrame from './ChartFrame.vue'

type Metric = 'spend' | 'revenue' | 'conversions' | 'roas'
const props = defineProps<{ report: TrendReport | null; loading?: boolean; currency: string; focus?: Channel | null; deltaSpend?: number | null }>()
const emit = defineEmits<{ focus: [c: Channel | null] }>()

const metric = ref<Metric>('spend')
const METRICS: { key: Metric; label: string }[] = [
  { key: 'spend', label: 'Spend' },
  { key: 'revenue', label: 'Revenue' },
  { key: 'conversions', label: 'Conversions' },
  { key: 'roas', label: 'ROAS' },
]

const days = computed(() => Array.from(new Set((props.report?.points ?? []).map((p) => p.day))).sort())
const channels = computed(() => {
  const totals = new Map<string, number>()
  for (const p of props.report?.points ?? []) totals.set(p.channel, (totals.get(p.channel) ?? 0) + p.spend)
  return [...totals.entries()].sort((a, b) => b[1] - a[1]).map(([c]) => c)
})
const empty = computed(() => !props.loading && (!props.report || props.report.points.length === 0))

const matrix = computed(() => {
  const m = new Map<string, Map<string, number | null>>()
  for (const c of channels.value) m.set(c, new Map())
  for (const p of props.report?.points ?? []) m.get(p.channel)?.set(p.day, p[metric.value] as number | null)
  return m
})

const fmt = (v: number | null) => {
  if (v === null || v === undefined) return '–'
  if (metric.value === 'spend' || metric.value === 'revenue') return money(v, props.currency, 0)
  if (metric.value === 'roas') return fmtRoas(v)
  return num(v)
}
const axisFmt = (v: number) => (metric.value === 'roas' ? `${v.toFixed(1)}×` : compact(v, metric.value === 'conversions' ? undefined : props.currency))

const option = computed(() => {
  const focus = props.focus
  return {
    ...animation(),
    grid: { left: 8, right: 16, top: 12, bottom: 8, containLabel: true },
    tooltip: {
      ...tooltipBase,
      valueFormatter: (v: number | null) => fmt(v),
    },
    legend: { show: false },
    xAxis: { type: 'category', data: days.value, ...axisBase, axisLabel: { ...chartText, formatter: (d: string) => shortDate(d), hideOverlap: true }, boundaryGap: false },
    yAxis: { type: 'value', ...axisBase, axisLabel: { ...chartText, formatter: axisFmt }, min: 0 },
    series: channels.value.map((c, i) => {
      const dim = focus && focus !== c
      return {
        name: channelLabel(c),
        type: 'line',
        showSymbol: false,
        smooth: 0.25,
        emphasis: { focus: 'series' },
        lineStyle: { width: focus === c ? 2.5 : 1.75, opacity: dim ? 0.3 : 1 },
        itemStyle: { color: seriesColor(c, i), opacity: dim ? 0.3 : 1 },
        endLabel: { show: days.value.length > 1, formatter: () => channelLabel(c), ...chartText, color: dim ? '#5a5957' : seriesColor(c, i), distance: 6, fontSize: 12 },
        data: days.value.map((d) => matrix.value.get(c)?.get(d) ?? null),
      }
    }),
  }
})

const title = computed(() => {
  const m = METRICS.find((x) => x.key === metric.value)!.label
  if (metric.value === 'spend' && props.deltaSpend !== null && props.deltaSpend !== undefined)
    return `Spend ${props.deltaSpend >= 0 ? 'up' : 'down'} ${pct(Math.abs(props.deltaSpend), 1)} vs the previous period`
  return `${m} by channel, daily`
})
const aria = computed(() => {
  const chans = channels.value.map((c) => channelLabel(c)).join(', ')
  return `Line chart of daily ${metric.value} for ${channels.value.length} channels (${chans}) over ${days.value.length} days. Use the Table toggle for exact values.`
})
</script>

<template>
  <ChartFrame :title="title" :subtitle="empty ? undefined : `${days.length} days · ${channels.length} channels`" :loading="loading" :empty="empty" :desc="aria" :height="300">
    <template #actions>
      <div class="seg" role="group" aria-label="Metric">
        <button v-for="m in METRICS" :key="m.key" type="button" :class="{ on: metric === m.key }" :aria-pressed="metric === m.key" @click="metric = m.key">{{ m.label }}</button>
      </div>
    </template>
    <VChart class="chart" :option="option" autoresize />
    <div class="legend" role="group" aria-label="Channels (click to focus)">
      <button v-for="(c, i) in channels" :key="c" type="button" class="chip" :class="{ dim: focus && focus !== c }" :aria-pressed="focus === c" @click="emit('focus', focus === c ? null : (c as Channel))">
        <i :style="{ background: seriesColor(c, i) }" aria-hidden="true" />{{ channelLabel(c) }}
      </button>
    </div>
    <template #table>
      <table class="dt">
        <caption class="sr-only">Daily {{ metric }} by channel</caption>
        <thead><tr><th scope="col">Day</th><th v-for="c in channels" :key="c" scope="col" class="num">{{ channelLabel(c) }}</th></tr></thead>
        <tbody>
          <tr v-for="d in days" :key="d"><td class="mono">{{ d }}</td><td v-for="c in channels" :key="c" class="num">{{ fmt(matrix.get(c)?.get(d) ?? null) }}</td></tr>
        </tbody>
      </table>
    </template>
  </ChartFrame>
</template>

<style scoped>
.chart { width: 100%; height: calc(100% - 30px); }
.legend { display: flex; flex-wrap: wrap; gap: 6px 12px; height: 30px; align-items: center; }
.chip { display: inline-flex; align-items: center; gap: 6px; background: none; border: 0; padding: 2px 4px; border-radius: 4px; font-size: var(--fs-12); color: var(--text); }
.chip i { width: 10px; height: 3px; border-radius: 2px; }
.chip.dim { color: var(--muted); }
.chip.dim i { opacity: 0.4; }
.chip:hover { color: var(--text-strong); }
.seg { display: inline-flex; border: 1px solid var(--border); border-radius: var(--r-sm); overflow: hidden; }
.seg button { height: 26px; padding: 0 9px; background: var(--surface-2); border: 0; color: var(--muted); font-size: var(--fs-12); font-weight: 500; }
.seg button + button { border-left: 1px solid var(--border); }
.seg button.on { background: var(--surface-3); color: var(--text-strong); }
.seg button:focus-visible { box-shadow: inset var(--ring); border-radius: 0; }
.dt { width: 100%; border-collapse: collapse; font-size: var(--fs-13); }
.dt th, .dt td { padding: 6px 10px; border-bottom: 1px solid var(--border); text-align: left; white-space: nowrap; }
.dt th { position: sticky; top: 0; background: var(--surface-2); color: var(--muted); font-weight: 500; font-size: var(--fs-12); }
.dt .num { text-align: right; font-variant-numeric: tabular-nums; }
@media (max-width: 640px) { .seg button { padding: 0 7px; } }
</style>
