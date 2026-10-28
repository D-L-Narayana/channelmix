<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { api, API_URL, lastCache, source } from './lib/api'
import type {
  Account,
  CampaignPerformanceRow,
  Channel,
  ChannelMixReport,
  DateRange,
  RecommendationRequest,
  RecommendationResponse,
  TrendReport,
} from './lib/types'
import { isoDaysAgo } from './lib/format'
import KpiCards from './components/KpiCards.vue'
import DateRangeFilter from './components/DateRangeFilter.vue'
import ChannelMixChart from './components/ChannelMixChart.vue'
import TrendChart from './components/TrendChart.vue'
import CampaignTable from './components/CampaignTable.vue'
import BudgetPanel from './components/BudgetPanel.vue'
import trendMock from './mock/trend.json'

const accounts = ref<Account[]>([])
const accountId = ref<number | null>(null)

// anchor "today" to the last day in the dataset so the demo always shows data
const mockDays = (trendMock as TrendReport).points.map((p) => p.day).sort()
const anchor = ref<string>(mockDays[mockDays.length - 1] ?? new Date().toISOString().slice(0, 10))
const range = ref<DateRange>({ start: isoDaysAgo(29, new Date(anchor.value)), end: anchor.value })
const selected = ref<Channel | null>(null)

const mix = ref<ChannelMixReport | null>(null)
const trend = ref<TrendReport | null>(null)
const campaigns = ref<CampaignPerformanceRow[]>([])
const rec = ref<RecommendationResponse | null>(null)
const loading = ref({ reports: false, rec: false })
const recError = ref<string | null>(null)
const lastRecRequest = ref<RecommendationRequest>({ lookback_days: 30, min_share: 0.05, max_shift_pct: 0.3 })

async function loadReports() {
  if (accountId.value === null) return
  loading.value.reports = true
  try {
    const id = accountId.value
    const [m, t, c] = await Promise.all([api.channelMix(id, range.value), api.trend(id, range.value), api.campaignReport(id, range.value)])
    mix.value = m
    trend.value = t
    campaigns.value = c
  } finally {
    loading.value.reports = false
  }
}

async function runRecommendation(req: RecommendationRequest = lastRecRequest.value) {
  if (accountId.value === null) return
  loading.value.rec = true
  recError.value = null
  lastRecRequest.value = req
  try {
    rec.value = await api.recommend(accountId.value, req)
  } catch (e) {
    recError.value = (e as Error).message
  } finally {
    loading.value.rec = false
  }
}

onMounted(async () => {
  const live = await api.probe()
  accounts.value = await api.accounts()
  accountId.value = accounts.value[0]?.id ?? null
  if (live) {
    const today = new Date().toISOString().slice(0, 10)
    anchor.value = today
    range.value = { start: isoDaysAgo(29), end: today }
  }
  await Promise.all([loadReports(), runRecommendation()])
})

watch([range, accountId], () => loadReports(), { deep: true })
watch(accountId, () => runRecommendation())
</script>

<template>
  <div class="app">
    <header class="top">
      <div class="brand">
        <img src="/favicon.svg" alt="" width="28" height="28" />
        <div>
          <h1>ChannelMix</h1>
          <div class="muted tagline">Cross-channel ad spend &amp; budget optimizer</div>
        </div>
      </div>
      <div class="right">
        <select v-if="accounts.length > 1" v-model="accountId" class="input">
          <option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.name }}</option>
        </select>
        <span v-else-if="accounts[0]" class="muted account">{{ accounts[0].name }} · {{ accounts[0].currency }}</span>
        <span class="badge" :class="source === 'api' ? 'good' : source === 'mock' ? 'warn' : 'neutral'" data-testid="source" :title="API_URL || 'VITE_API_URL not set'">
          <i class="dot" />
          {{ source === 'api' ? 'live API' : source === 'mock' ? 'demo data' : 'connecting…' }}
          <span v-if="source === 'api' && lastCache" class="mono">· cache {{ lastCache }}</span>
        </span>
        <a class="btn gh" href="https://github.com/D-L-Narayana/channelmix" target="_blank" rel="noreferrer">GitHub</a>
      </div>
    </header>

    <main>
      <div class="toolbar">
        <DateRangeFilter v-model="range" :anchor="anchor" />
        <span v-if="selected" class="badge" style="cursor: pointer" @click="selected = null">filter: {{ selected }} ✕</span>
      </div>

      <KpiCards :report="mix" :loading="loading.reports" />

      <div class="grid-2">
        <ChannelMixChart :report="mix" :loading="loading.reports" :selected="selected" @select="selected = $event" />
        <TrendChart :report="trend" :loading="loading.reports" :selected="selected" />
      </div>

      <BudgetPanel :result="rec" :loading="loading.rec" :error="recError" @run="runRecommendation" />

      <CampaignTable v-model:selected="selected" :rows="campaigns" :loading="loading.reports" />
    </main>

    <footer class="muted">
      FastAPI · SQLAlchemy 2 · PostgreSQL · Redis · Vue 3 + Vite + TypeScript · ECharts · pytest-bdd · Vitest · ELK
      <span v-if="source === 'mock'"> — running on bundled demo data generated by the API's seed script</span>
    </footer>
  </div>
</template>

<style scoped>
.app { max-width: 1320px; margin: 0 auto; padding: 18px 22px 40px; }
.top { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 6px 0 18px; }
.brand { display: flex; align-items: center; gap: 12px; }
.tagline { font-size: 12px; }
.right { display: flex; align-items: center; gap: 10px; }
.account { font-size: 12.5px; }
.gh { text-decoration: none; }
main { display: flex; flex-direction: column; gap: 16px; }
.toolbar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
footer { margin-top: 28px; font-size: 12px; text-align: center; }
</style>
