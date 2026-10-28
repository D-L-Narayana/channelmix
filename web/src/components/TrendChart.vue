<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent, GridComponent, DataZoomComponent } from 'echarts/components'
import type { TrendReport, Channel } from '../lib/types'
import { CHANNEL_COLORS, CHANNEL_LABELS } from '../lib/format'

use([CanvasRenderer, LineChart, BarChart, TooltipComponent, LegendComponent, GridComponent, DataZoomComponent])

const props = defineProps<{ report: TrendReport | null; loading?: boolean; selected?: Channel | null }>()
const smooth = ref(true)

const days = computed(() => [...new Set((props.report?.points ?? []).map((p) => p.day))].sort())
const channels = computed(() => {
  const all = [...new Set((props.report?.points ?? []).map((p) => p.channel))]
  return props.selected ? all.filter((c) => c === props.selected) : all
})

function seriesFor(channel: string, key: 'spend' | 'spend_7d_avg' | 'roas' | 'roas_7d') {
  const idx = new Map((props.report?.points ?? []).filter((p) => p.channel === channel).map((p) => [p.day, p]))
  return days.value.map((d) => idx.get(d)?.[key] ?? null)
}

const option = computed(() => ({
  tooltip: {
    trigger: 'axis',
    valueFormatter: (v: number | null) => (v === null ? '–' : v >= 50 ? `$${Math.round(v).toLocaleString()}` : `${v.toFixed(2)}x`),
  },
  legend: { top: 0, icon: 'roundRect', type: 'scroll', right: 0, left: 0 },
  grid: { left: 8, right: 8, top: 40, bottom: 44, containLabel: true },
  dataZoom: [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 6, borderColor: 'transparent' }],
  xAxis: { type: 'category', data: days.value, axisTick: { show: false }, axisLabel: { formatter: (d: string) => d.slice(5) } },
  yAxis: [
    { type: 'value', axisLabel: { formatter: (v: number) => `$${v >= 1000 ? `${v / 1000}k` : v}` }, splitLine: { lineStyle: { color: '#eef2f7' } } },
    { type: 'value', axisLabel: { formatter: (v: number) => `${v}x` }, splitLine: { show: false }, min: 0 },
  ],
  series: channels.value.flatMap((c) => [
    {
      name: `${CHANNEL_LABELS[c] ?? c} spend`,
      type: 'bar',
      stack: 'spend',
      barMaxWidth: 18,
      itemStyle: { color: CHANNEL_COLORS[c], opacity: 0.55, borderRadius: 2 },
      data: seriesFor(c, 'spend'),
    },
    {
      name: `${CHANNEL_LABELS[c] ?? c} ROAS (7d)`,
      type: 'line',
      yAxisIndex: 1,
      smooth: smooth.value,
      showSymbol: false,
      lineStyle: { width: 2.2, color: CHANNEL_COLORS[c] },
      itemStyle: { color: CHANNEL_COLORS[c] },
      data: seriesFor(c, 'roas_7d'),
    },
  ]),
}))
</script>

<template>
  <section class="card" data-testid="trend">
    <div class="card-head">
      <div>
        <h2>Spend &amp; ROAS trend</h2>
        <div class="sub">Daily spend (stacked bars) and 7-day rolling ROAS (lines) · computed with SQL window functions</div>
      </div>
      <label class="toggle muted"><input v-model="smooth" type="checkbox" /> smooth</label>
    </div>
    <div v-if="loading || !report" class="skeleton" style="height: 320px" />
    <div v-else-if="!days.length" class="empty muted">No data in this range.</div>
    <v-chart v-else class="chart" :option="option" autoresize />
  </section>
</template>

<style scoped>
.chart { height: 320px; }
.toggle { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; }
.empty { height: 320px; display: grid; place-items: center; }
</style>
