<script setup lang="ts">
/**
 * By-channel stacked bar: share of spend vs share of revenue (two 100% stacked bars).
 * A channel whose revenue segment is wider than its spend segment is pulling its weight.
 */
import { computed } from 'vue'
import VChart from 'vue-echarts'
import '../lib/echarts'
import { animation, axisBase, chartText, tooltipBase } from '../lib/echarts'
import type { Channel, ChannelMixReport } from '../lib/types'
import { channelLabel, money, num, pct, roas as fmtRoas, seriesColor } from '../lib/format'
import ChartFrame from './ChartFrame.vue'

const props = defineProps<{ report: ChannelMixReport | null; loading?: boolean; currency: string; focus?: Channel | null }>()
const emit = defineEmits<{ focus: [c: Channel | null] }>()

const rows = computed(() => [...(props.report?.channels ?? [])].sort((a, b) => b.spend - a.spend))
const empty = computed(() => !props.loading && rows.value.length === 0)

const option = computed(() => ({
  ...animation(),
  grid: { left: 8, right: 16, top: 8, bottom: 8, containLabel: true },
  tooltip: {
    ...tooltipBase,
    axisPointer: { type: 'shadow' },
    formatter: (params: { seriesName: string; value: number; axisValue: string; color: string }[]) =>
      `<div style="margin-bottom:4px;color:#8f8e8b">${params[0]?.axisValue}</div>` +
      params
        .filter((p) => p.value > 0)
        .map((p) => `<div style="display:flex;gap:10px;justify-content:space-between"><span><i style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${p.color};margin-right:6px"></i>${p.seriesName}</span><b>${pct(p.value, 1)}</b></div>`)
        .join(''),
  },
  xAxis: { type: 'value', max: 1, ...axisBase, axisLabel: { ...chartText, formatter: (v: number) => `${Math.round(v * 100)}%` }, splitLine: { show: false } },
  yAxis: { type: 'category', data: ['Spend', 'Revenue'], ...axisBase, axisLabel: { ...chartText, color: '#cdccca', fontWeight: 500 }, inverse: true },
  series: rows.value.map((r, i) => {
    const dim = props.focus && props.focus !== r.channel
    return {
      name: channelLabel(r.channel),
      type: 'bar',
      stack: 'share',
      barWidth: 34,
      itemStyle: { color: seriesColor(r.channel, i), opacity: dim ? 0.3 : 1, borderColor: '#1c1b19', borderWidth: 1 },
      label: {
        show: true,
        position: 'inside',
        formatter: (p: { value: number }) => (p.value >= 0.08 ? `${channelLabel(r.channel)} ${Math.round(p.value * 100)}%` : p.value >= 0.04 ? `${Math.round(p.value * 100)}%` : ''),
        color: '#1b1407',
        fontSize: 12,
        fontWeight: 500,
        fontFamily: chartText.fontFamily,
      },
      emphasis: { focus: 'series' },
      data: [r.spend_share, r.revenue_share],
    }
  }),
}))

const insight = computed(() => {
  if (!rows.value.length) return 'Share of spend vs share of revenue by channel'
  const best = [...rows.value].sort((a, b) => b.revenue_share - b.spend_share - (a.revenue_share - a.spend_share))[0]
  const gap = best.revenue_share - best.spend_share
  if (Math.abs(gap) < 0.02 || !props.report?.total_revenue) {
    const top = rows.value[0]
    return `${channelLabel(top.channel)} takes ${pct(top.spend_share, 0)} of spend`
  }
  return `${channelLabel(best.channel)} takes ${pct(best.spend_share, 0)} of spend but ${pct(best.revenue_share, 0)} of revenue`
})
const aria = computed(
  () =>
    `Two stacked bars comparing each channel's share of spend and share of revenue. ` +
    rows.value.map((r) => `${channelLabel(r.channel)}: ${pct(r.spend_share, 0)} of spend, ${pct(r.revenue_share, 0)} of revenue, ROAS ${fmtRoas(r.roas)}`).join('; '),
)
</script>

<template>
  <ChartFrame :title="insight" :subtitle="empty ? undefined : 'Share of spend vs share of revenue'" :loading="loading" :empty="empty" :desc="aria" :height="300">
    <VChart class="chart" :option="option" autoresize />
    <ul class="list" aria-label="Channels">
      <li v-for="(r, i) in rows" :key="r.channel">
        <button type="button" class="item" :class="{ dim: focus && focus !== r.channel }" :aria-pressed="focus === r.channel" @click="emit('focus', focus === r.channel ? null : r.channel)">
          <i :style="{ background: seriesColor(r.channel, i) }" aria-hidden="true" />
          <span class="name">{{ channelLabel(r.channel) }}</span>
          <span class="num v">{{ money(r.spend, currency) }}</span>
          <span class="num v muted">ROAS {{ fmtRoas(r.roas) }}</span>
        </button>
      </li>
    </ul>
    <template #table>
      <table class="dt">
        <caption class="sr-only">Channel mix</caption>
        <thead><tr><th scope="col">Channel</th><th class="num" scope="col">Spend</th><th class="num" scope="col">Spend share</th><th class="num" scope="col">Revenue</th><th class="num" scope="col">Rev. share</th><th class="num" scope="col">ROAS</th><th class="num" scope="col">CPA</th><th class="num" scope="col">Conv.</th></tr></thead>
        <tbody>
          <tr v-for="r in rows" :key="r.channel">
            <td>{{ channelLabel(r.channel) }}</td><td class="num">{{ money(r.spend, currency) }}</td><td class="num">{{ pct(r.spend_share) }}</td>
            <td class="num">{{ money(r.revenue, currency) }}</td><td class="num">{{ pct(r.revenue_share) }}</td><td class="num">{{ fmtRoas(r.roas) }}</td>
            <td class="num">{{ money(r.cpa, currency, 2) }}</td><td class="num">{{ num(r.conversions) }}</td>
          </tr>
        </tbody>
      </table>
    </template>
  </ChartFrame>
</template>

<style scoped>
.chart { width: 100%; height: 150px; }
.list { display: flex; flex-direction: column; gap: 2px; margin-top: 6px; }
.item { width: 100%; display: grid; grid-template-columns: 10px 1fr auto auto; gap: 10px; align-items: center; padding: 6px 6px; border: 0; background: none; border-radius: var(--r-sm); font-size: var(--fs-13); color: var(--text); text-align: left; }
.item:hover { background: var(--surface-2); color: var(--text-strong); }
.item.dim { opacity: 0.5; }
.item i { width: 10px; height: 10px; border-radius: 2px; }
.v { font-variant-numeric: tabular-nums; min-width: 68px; text-align: right; }
.dt { width: 100%; border-collapse: collapse; font-size: var(--fs-13); }
.dt th, .dt td { padding: 6px 10px; border-bottom: 1px solid var(--border); text-align: left; white-space: nowrap; }
.dt th { position: sticky; top: 0; background: var(--surface-2); color: var(--muted); font-weight: 500; font-size: var(--fs-12); }
.dt .num { text-align: right; font-variant-numeric: tabular-nums; }
</style>
