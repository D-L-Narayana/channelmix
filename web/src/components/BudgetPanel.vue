<script setup lang="ts">
/** Budget reallocation from GET /recommendations with per-channel explanations. */
import { computed, ref, watch } from 'vue'
import type { RecommendationRequest, RecommendationResponse } from '../lib/types'
import type { ApiError } from '../lib/api'
import { channelLabel, money, pct, roas as fmtRoas, seriesColor } from '../lib/format'
import Card from './ui/Card.vue'
import Button from './ui/Button.vue'
import Input from './ui/Input.vue'
import Select from './ui/Select.vue'
import Skeleton from './ui/Skeleton.vue'
import EmptyState from './ui/EmptyState.vue'
import ErrorState from './ErrorState.vue'

const props = defineProps<{ result: RecommendationResponse | null; loading?: boolean; error?: ApiError | null; currency: string; request: RecommendationRequest; hasData: boolean }>()
const emit = defineEmits<{ run: [req: RecommendationRequest] }>()

const budget = ref<string>(props.request.total_budget ? String(props.request.total_budget) : '')
const lookback = ref(String(props.request.lookback_days ?? 30))
const shift = ref(props.request.max_shift_pct === null || props.request.max_shift_pct === undefined ? '' : String(props.request.max_shift_pct))
watch(
  () => props.result,
  (r) => {
    if (r && !budget.value) budget.value = String(Math.round(r.total_budget))
  },
)

function run() {
  const b = Number(budget.value)
  emit('run', {
    total_budget: budget.value && b > 0 ? b : null,
    lookback_days: Number(lookback.value),
    min_share: 0.05,
    max_shift_pct: shift.value === '' ? null : Number(shift.value),
  })
}

const rows = computed(() => [...(props.result?.channels ?? [])].sort((a, b) => b.recommended_daily_spend - a.recommended_daily_spend))
const maxSpend = computed(() => Math.max(1, ...rows.value.flatMap((r) => [r.current_daily_spend, r.recommended_daily_spend])))
const uplift = computed(() => props.result?.projected_uplift ?? 0)
const weakFit = computed(() => rows.value.filter((r) => r.curve.n_points < 7 || (r.curve.r2 !== null && r.curve.r2 < 0.3)).length)
const title = computed(() => {
  if (!props.result) return 'Budget reallocation'
  if (Math.abs(uplift.value) < 1) return 'Current split is already close to optimal'
  return `Reallocating ${money(props.result.total_budget, props.currency)}/day could add ${money(uplift.value, props.currency)}/day (${pct(props.result.projected_uplift_pct, 1, true)})`
})
</script>

<template>
  <Card :title="title" :subtitle="result ? `Lookback ${result.lookback_days}d · ${result.window_start} → ${result.window_end} · ${result.method}` : 'Marginal-ROAS allocation across channels from your own history'">
    <form class="controls" @submit.prevent="run">
      <Input v-model="budget" type="number" size="sm" inputmode="decimal" min="1" step="1" :label="`Daily budget (${currency})`" placeholder="current avg" aria-label="Daily budget" />
      <Select v-model="lookback" size="sm" label="Lookback" :options="[14, 30, 60, 90].map((d) => ({ value: String(d), label: `${d} days` }))" />
      <Select v-model="shift" size="sm" label="Max shift per channel" :options="[{ value: '', label: 'No cap' }, { value: '0.1', label: '±10%' }, { value: '0.2', label: '±20%' }, { value: '0.3', label: '±30%' }, { value: '0.5', label: '±50%' }]" />
      <Button type="submit" variant="primary" size="md" :loading="loading" :disabled="!hasData">Recompute</Button>
    </form>

    <div v-if="loading && !result" class="sk" aria-busy="true">
      <div v-for="i in 3" :key="i" class="skrow"><Skeleton width="90px" height="14px" /><Skeleton height="10px" /><Skeleton width="100%" height="12px" /></div>
    </div>
    <ErrorState v-else-if="error" :error="error" compact :retry="run" />
    <EmptyState v-else-if="!hasData" compact title="Nothing to optimise yet" body="Recommendations need at least a week of daily spend and revenue per channel. Import data first." />
    <EmptyState v-else-if="result && !rows.length" compact title="Not enough history" body="The optimiser needs at least a week of daily spend and revenue per channel. Extend the lookback or import more days." />
    <template v-else-if="result">
      <p class="summary">{{ result.summary }}</p>
      <ul class="recs">
        <li v-for="(r, i) in rows" :key="r.channel" class="rec">
          <div class="head">
            <span class="ch"><i :style="{ background: seriesColor(r.channel, i) }" aria-hidden="true" />{{ channelLabel(r.channel) }}</span>
            <span class="nums num">
              <span class="muted">{{ money(r.current_daily_spend, currency) }}</span>
              <span class="arr" aria-hidden="true">→</span>
              <span class="strong">{{ money(r.recommended_daily_spend, currency) }}/day</span>
              <span class="d" :class="r.delta > 0 ? 'up' : r.delta < 0 ? 'down' : ''">{{ r.delta > 0 ? '↑' : r.delta < 0 ? '↓' : '→' }} {{ pct(r.delta_pct, 0, true) }}</span>
            </span>
          </div>
          <div class="bars" aria-hidden="true">
            <span class="b cur" :style="{ width: (r.current_daily_spend / maxSpend) * 100 + '%' }" />
            <span class="b rec" :style="{ width: (r.recommended_daily_spend / maxSpend) * 100 + '%', background: seriesColor(r.channel, i) }" />
          </div>
          <p class="why">{{ r.explanation }}</p>
          <p class="fit mono">marginal ROAS {{ fmtRoas(r.marginal_roas_at_current) }} → {{ fmtRoas(r.marginal_roas_at_recommended) }} · fit r² {{ r.curve.r2 === null ? '–' : r.curve.r2.toFixed(2) }} on {{ r.curve.n_points }} days</p>
        </li>
      </ul>
      <p v-if="weakFit" class="caveat">{{ weakFit }} channel{{ weakFit > 1 ? 's have' : ' has' }} a weak response-curve fit (few days or low r²) — treat those suggestions as directional.</p>
    </template>
  </Card>
</template>

<style scoped>
.controls { display: grid; grid-template-columns: 160px 140px 170px auto; gap: 12px; align-items: end; margin-bottom: 18px; }
.controls :deep(.field) { display: flex; }
.summary { font-size: var(--fs-14); color: var(--text); line-height: 1.55; max-width: 72ch; margin-bottom: 14px; }
.recs { display: flex; flex-direction: column; gap: 14px; }
.rec { padding: 12px 14px; border: 1px solid var(--border); border-radius: var(--r-md); background: var(--surface-2); }
.head { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; flex-wrap: wrap; }
.ch { display: inline-flex; align-items: center; gap: 8px; font-weight: 500; color: var(--text-strong); }
.ch i { width: 10px; height: 10px; border-radius: 2px; }
.nums { display: inline-flex; gap: 8px; align-items: baseline; font-size: var(--fs-14); }
.arr { color: var(--faint); }
.d { font-size: var(--fs-12); font-weight: 500; color: var(--muted); }
.d.up { color: var(--success); }
.d.down { color: var(--error); }
.bars { position: relative; height: 10px; margin: 10px 0 8px; background: var(--surface-3); border-radius: 3px; overflow: hidden; }
.b { position: absolute; left: 0; top: 0; height: 100%; border-radius: 3px; transition: width var(--t-slow) var(--ease); }
.b.cur { background: var(--border-strong); height: 100%; }
.b.rec { height: 50%; top: 25%; }
.why { font-size: var(--fs-13); color: var(--text); line-height: 1.5; }
.fit { font-size: var(--fs-12); color: var(--muted); margin-top: 6px; }
.caveat { margin-top: 12px; font-size: var(--fs-12); color: var(--warning-text); }
.sk { display: flex; flex-direction: column; gap: 14px; }
.skrow { display: flex; flex-direction: column; gap: 8px; padding: 12px 14px; border: 1px solid var(--border); border-radius: var(--r-md); }
@media (max-width: 900px) { .controls { grid-template-columns: 1fr 1fr; } }
</style>
