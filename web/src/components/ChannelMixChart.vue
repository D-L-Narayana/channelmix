<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, BarChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import type { ChannelMixReport, Channel } from '../lib/types'
import { CHANNEL_COLORS, CHANNEL_LABELS, money, pct, roas } from '../lib/format'

use([CanvasRenderer, PieChart, BarChart, TooltipComponent, LegendComponent, GridComponent])

const props = defineProps<{ report: ChannelMixReport | null; loading?: boolean; selected?: Channel | null }>()
const emit = defineEmits<{ select: [Channel | null] }>()

const mode = ref<'donut' | 'bar'>('donut')
const metric = ref<'spend' | 'revenue'>('spend')

const rows = computed(() => props.report?.channels ?? [])

const donutOption = computed(() => ({
  tooltip: {
    trigger: 'item',
    formatter: (p: { name: string; value: number; percent: number }) =>
      `<b>${CHANNEL_LABELS[p.name] ?? p.name}</b><br/>${money(p.value)} · ${p.percent.toFixed(1)}%`,
  },
  legend: { bottom: 0, icon: 'circle', formatter: (n: string) => CHANNEL_LABELS[n] ?? n },
  series: [
    {
      type: 'pie',
      radius: ['58%', '82%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      emphasis: { label: { show: false }, scale: true, scaleSize: 6 },
      data: rows.value.map((r) => ({
        name: r.channel,
        value: r[metric.value],
        itemStyle: { color: CHANNEL_COLORS[r.channel], opacity: props.selected && props.selected !== r.channel ? 0.35 : 1 },
      })),
    },
  ],
}))

const barOption = computed(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  legend: { bottom: 0, icon: 'roundRect' },
  grid: { left: 8, right: 16, top: 24, bottom: 36, containLabel: true },
  xAxis: { type: 'category', data: rows.value.map((r) => CHANNEL_LABELS[r.channel] ?? r.channel), axisTick: { show: false } },
  yAxis: [
    { type: 'value', axisLabel: { formatter: (v: number) => `$${v / 1000}k` }, splitLine: { lineStyle: { color: '#eef2f7' } } },
    { type: 'value', axisLabel: { formatter: (v: number) => `${v}x` }, splitLine: { show: false } },
  ],
  series: [
    {
      name: 'Spend',
      type: 'bar',
      barMaxWidth: 46,
      itemStyle: { borderRadius: [6, 6, 0, 0], color: '#94a3b8' },
      data: rows.value.map((r) => r.spend),
    },
    {
      name: 'Revenue',
      type: 'bar',
      barMaxWidth: 46,
      itemStyle: { borderRadius: [6, 6, 0, 0] },
      data: rows.value.map((r) => ({ value: r.revenue, itemStyle: { color: CHANNEL_COLORS[r.channel] } })),
    },
    {
      name: 'ROAS',
      type: 'bar',
      yAxisIndex: 1,
      barMaxWidth: 18,
      itemStyle: { borderRadius: [6, 6, 0, 0], color: '#0f172a' },
      data: rows.value.map((r) => r.roas ?? 0),
    },
  ],
}))

const total = computed(() => (metric.value === 'spend' ? props.report?.total_spend : props.report?.total_revenue) ?? 0)

function onClick(params: { name?: string }) {
  const ch = params.name as Channel | undefined
  if (!ch) return
  emit('select', props.selected === ch ? null : ch)
}
</script>

<template>
  <section class="card" data-testid="channel-mix">
    <div class="card-head">
      <div>
        <h2>Channel mix</h2>
        <div class="sub">Share of {{ metric }} by channel · click a slice to drill down</div>
      </div>
      <div class="controls">
        <div class="seg">
          <button class="btn" :class="{ active: metric === 'spend' }" @click="metric = 'spend'">Spend</button>
          <button class="btn" :class="{ active: metric === 'revenue' }" @click="metric = 'revenue'">Revenue</button>
        </div>
        <div class="seg">
          <button class="btn" :class="{ active: mode === 'donut' }" data-testid="mode-donut" @click="mode = 'donut'">Donut</button>
          <button class="btn" :class="{ active: mode === 'bar' }" data-testid="mode-bar" @click="mode = 'bar'">Bar</button>
        </div>
      </div>
    </div>

    <div v-if="loading || !report" class="skeleton" style="height: 260px" />
    <div v-else-if="!rows.length" class="empty muted">No data in this range.</div>
    <div v-else class="body">
      <div class="chart-wrap">
        <v-chart v-if="mode === 'donut'" class="chart" :option="donutOption" autoresize @click="onClick" />
        <v-chart v-else class="chart" :option="barOption" autoresize />
        <div v-if="mode === 'donut'" class="center">
          <div class="muted" style="font-size: 11px">Total {{ metric }}</div>
          <div class="center-val">{{ money(total) }}</div>
        </div>
      </div>
      <table class="table mix-table" data-testid="mix-table">
        <thead>
          <tr><th class="left">Channel</th><th>Spend</th><th>Share</th><th>ROAS</th><th>CPA</th></tr>
        </thead>
        <tbody>
          <tr
            v-for="r in rows"
            :key="r.channel"
            :class="{ dim: selected && selected !== r.channel, sel: selected === r.channel }"
            @click="emit('select', selected === r.channel ? null : r.channel)"
          >
            <td class="left"><span class="chip"><i class="sw" :style="{ background: CHANNEL_COLORS[r.channel] }" />{{ CHANNEL_LABELS[r.channel] }}</span></td>
            <td>{{ money(r.spend) }}</td>
            <td>{{ pct(r.spend_share) }}</td>
            <td :class="r.roas_rank === 1 ? 'good' : ''">{{ roas(r.roas) }}</td>
            <td>{{ money(r.cpa, 2) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.controls { display: flex; gap: 8px; }
.seg { display: inline-flex; gap: 2px; border: 1px solid var(--border); border-radius: 10px; padding: 2px; }
.seg .btn { border: 0; padding: 4px 10px; font-size: 12.5px; border-radius: 8px; }
.body { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; align-items: center; }
.chart-wrap { position: relative; height: 260px; }
.chart { height: 260px; }
.center { position: absolute; left: 50%; top: 45%; transform: translate(-50%, -50%); text-align: center; pointer-events: none; }
.center-val { font-size: 18px; font-weight: 650; letter-spacing: -0.02em; }
.mix-table tbody tr { cursor: pointer; }
.mix-table tr.dim { opacity: .45; }
.mix-table tr.sel td { background: #f0f9ff; }
.empty { height: 260px; display: grid; place-items: center; }
@media (max-width: 900px) { .body { grid-template-columns: 1fr; } }
</style>
