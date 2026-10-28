<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import type { RecommendationRequest, RecommendationResponse } from '../lib/types'
import { CHANNEL_COLORS, CHANNEL_LABELS, money, pct, roas } from '../lib/format'

use([CanvasRenderer, BarChart, TooltipComponent, LegendComponent, GridComponent])

const props = defineProps<{ result: RecommendationResponse | null; loading?: boolean; error?: string | null }>()
const emit = defineEmits<{ run: [RecommendationRequest] }>()

const budget = ref<number | null>(null)
const maxShift = ref<number>(30)
const minShare = ref<number>(5)
const lookback = ref<number>(30)
const open = ref<string | null>(null)

watch(
  () => props.result,
  (r) => {
    if (r && budget.value === null) budget.value = Math.round(r.total_budget)
  },
  { immediate: true },
)

function run() {
  emit('run', {
    total_budget: budget.value ?? undefined,
    lookback_days: lookback.value,
    min_share: minShare.value / 100,
    max_shift_pct: maxShift.value >= 100 ? null : maxShift.value / 100,
  })
}

const rows = computed(() => props.result?.channels ?? [])

const option = computed(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v: number) => money(v) },
  legend: { bottom: 0, icon: 'roundRect' },
  grid: { left: 8, right: 16, top: 12, bottom: 36, containLabel: true },
  xAxis: { type: 'value', axisLabel: { formatter: (v: number) => `$${v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v}` }, splitLine: { lineStyle: { color: '#eef2f7' } } },
  yAxis: { type: 'category', data: rows.value.map((r) => CHANNEL_LABELS[r.channel] ?? r.channel), axisTick: { show: false } },
  series: [
    { name: 'Current / day', type: 'bar', barMaxWidth: 16, itemStyle: { color: '#cbd5e1', borderRadius: 4 }, data: rows.value.map((r) => r.current_daily_spend) },
    {
      name: 'Recommended / day',
      type: 'bar',
      barMaxWidth: 16,
      itemStyle: { borderRadius: 4 },
      data: rows.value.map((r) => ({ value: r.recommended_daily_spend, itemStyle: { color: CHANNEL_COLORS[r.channel] } })),
    },
  ],
}))
</script>

<template>
  <section class="card" data-testid="budget-panel">
    <div class="card-head">
      <div>
        <h2>Budget reallocation</h2>
        <div class="sub">Diminishing-returns ROAS curve per channel fitted from history · greedy marginal allocation</div>
      </div>
      <span v-if="result" class="badge" :class="result.projected_uplift >= 0 ? 'good' : 'warn'" data-testid="uplift">
        projected {{ pct(result.projected_uplift_pct, 1, true) }} revenue · {{ money(result.projected_uplift) }}/day
      </span>
    </div>

    <form class="controls" @submit.prevent="run">
      <label>
        <span>Daily budget</span>
        <div class="money"><span class="muted">$</span><input v-model.number="budget" class="input" type="number" min="1" step="50" data-testid="budget-input" /></div>
      </label>
      <label>
        <span>Max shift per channel: <b>{{ maxShift >= 100 ? 'unlimited' : `±${maxShift}%` }}</b></span>
        <input v-model.number="maxShift" type="range" min="5" max="100" step="5" data-testid="max-shift" />
      </label>
      <label>
        <span>Floor per channel: <b>{{ minShare }}%</b></span>
        <input v-model.number="minShare" type="range" min="0" max="30" step="1" />
      </label>
      <label>
        <span>Lookback</span>
        <select v-model.number="lookback" class="input">
          <option :value="14">14 days</option>
          <option :value="30">30 days</option>
          <option :value="60">60 days</option>
          <option :value="90">90 days</option>
        </select>
      </label>
      <button class="btn primary" type="submit" :disabled="loading" data-testid="run">{{ loading ? 'Optimising…' : 'Recompute' }}</button>
    </form>

    <div v-if="error" class="error">{{ error }}</div>
    <div v-if="loading && !result" class="skeleton" style="height: 280px" />
    <div v-else-if="result" class="body">
      <div>
        <v-chart class="chart" :option="option" autoresize />
        <p class="summary" data-testid="summary">{{ result.summary }}</p>
        <p class="muted method">Method: {{ result.method }} · window {{ result.window_start }} → {{ result.window_end }}</p>
      </div>

      <div class="recs">
        <article
          v-for="r in rows"
          :key="r.channel"
          class="rec"
          :class="{ open: open === r.channel }"
          data-testid="recommendation"
          @click="open = open === r.channel ? null : r.channel"
        >
          <header>
            <span class="chip"><i class="sw" :style="{ background: CHANNEL_COLORS[r.channel] }" />{{ CHANNEL_LABELS[r.channel] }}</span>
            <span class="delta" :class="r.delta > 0 ? 'good' : r.delta < 0 ? 'bad' : 'muted'" data-testid="delta">
              {{ r.delta > 0 ? '+' : '' }}{{ money(r.delta) }}/day <small>({{ pct(r.delta_pct, 0, true) }})</small>
            </span>
          </header>
          <div class="nums">
            <div><span class="muted">Current</span><b>{{ money(r.current_daily_spend) }}</b></div>
            <div><span class="muted">Recommended</span><b>{{ money(r.recommended_daily_spend) }}</b></div>
            <div><span class="muted">ROAS</span><b>{{ roas(r.current_roas) }}</b></div>
            <div><span class="muted">Marginal ROAS</span><b>{{ roas(r.marginal_roas_at_current) }} → {{ roas(r.marginal_roas_at_recommended) }}</b></div>
          </div>
          <p class="explain" data-testid="explanation">{{ r.explanation }}</p>
          <div v-if="open === r.channel" class="curve mono">
            revenue(spend) = {{ r.curve.a.toFixed(3) }} · spend<sup>{{ r.curve.b.toFixed(3) }}</sup>
            &nbsp;·&nbsp; fit: {{ r.curve.method }}, n={{ r.curve.n_points }}<span v-if="r.curve.r2 !== null">, R²={{ r.curve.r2 }}</span>
            &nbsp;·&nbsp; projected revenue {{ money(r.projected_daily_revenue) }}/day
          </div>
        </article>
      </div>
    </div>
  </section>
</template>

<style scoped>
.controls { display: grid; grid-template-columns: 1.1fr 1.4fr 1.2fr .9fr auto; gap: 14px; align-items: end; padding: 12px 14px; background: #f8fafc; border: 1px solid var(--border); border-radius: 12px; margin-bottom: 14px; }
.controls label { display: flex; flex-direction: column; gap: 5px; font-size: 12px; color: var(--muted); }
.controls label b { color: var(--text); }
.controls input[type=range] { accent-color: var(--accent); }
.money { display: flex; align-items: center; gap: 6px; }
.money .input { width: 100%; }
.body { display: grid; grid-template-columns: 1fr 1.2fr; gap: 18px; }
.chart { height: 190px; }
.summary { margin: 8px 0 4px; font-weight: 500; line-height: 1.5; }
.method { font-size: 11.5px; margin: 0; }
.recs { display: flex; flex-direction: column; gap: 10px; }
.rec { border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px; cursor: pointer; transition: border-color .15s, box-shadow .15s; }
.rec:hover, .rec.open { border-color: #bae6fd; box-shadow: 0 0 0 3px #f0f9ff; }
.rec header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.rec .delta { font-weight: 650; font-variant-numeric: tabular-nums; }
.rec .delta small { font-weight: 500; }
.nums { display: grid; grid-template-columns: repeat(4, auto); gap: 6px 18px; font-size: 12.5px; }
.nums div { display: flex; flex-direction: column; }
.nums b { font-variant-numeric: tabular-nums; }
.explain { margin: 10px 0 0; font-size: 12.5px; color: #334155; line-height: 1.5; }
.curve { margin-top: 8px; padding: 8px 10px; background: #f8fafc; border-radius: 8px; color: var(--muted); }
.error { color: var(--bad); background: #fef2f2; padding: 10px 12px; border-radius: 10px; margin-bottom: 12px; }
.sw { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }
@media (max-width: 1100px) { .controls { grid-template-columns: 1fr 1fr; } .body { grid-template-columns: 1fr; } }
</style>
