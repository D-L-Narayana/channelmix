<script setup lang="ts">
import { computed } from 'vue'
import type { ChannelMixReport } from '../lib/types'
import { money, num, roas } from '../lib/format'

const props = defineProps<{ report: ChannelMixReport | null; loading?: boolean }>()

const kpis = computed(() => {
  const r = props.report
  if (!r) return []
  const conv = r.channels.reduce((a, c) => a + c.conversions, 0)
  const clicks = r.channels.reduce((a, c) => a + c.clicks, 0)
  const impr = r.channels.reduce((a, c) => a + c.impressions, 0)
  const best = [...r.channels].sort((a, b) => a.roas_rank - b.roas_rank)[0]
  return [
    { label: 'Total spend', value: money(r.total_spend), sub: `${r.start} → ${r.end}` },
    { label: 'Revenue', value: money(r.total_revenue), sub: `${num(conv)} conversions` },
    { label: 'Blended ROAS', value: roas(r.blended_roas), sub: best ? `best: ${best.channel} ${roas(best.roas)}` : '' },
    { label: 'CPA', value: conv ? money(r.total_spend / conv, 2) : '–', sub: `CTR ${impr ? ((clicks / impr) * 100).toFixed(2) : '–'}%` },
  ]
})
</script>

<template>
  <div class="kpis" data-testid="kpis">
    <template v-if="loading || !report">
      <div v-for="i in 4" :key="i" class="card kpi"><div class="skeleton" style="height: 54px" /></div>
    </template>
    <div v-else v-for="k in kpis" :key="k.label" class="card kpi">
      <div class="label">{{ k.label }}</div>
      <div class="value">{{ k.value }}</div>
      <div class="sub muted">{{ k.sub }}</div>
    </div>
  </div>
</template>

<style scoped>
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.kpi { padding: 16px 18px; }
.label { font-size: 12px; color: var(--muted); font-weight: 500; }
.value { font-size: 24px; font-weight: 650; letter-spacing: -0.02em; margin: 4px 0 2px; font-variant-numeric: tabular-nums; }
.sub { font-size: 12px; }
@media (max-width: 900px) { .kpis { grid-template-columns: repeat(2, 1fr); } }
</style>
