<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useWorkspaceStore } from '../stores/workspace'
import { useLiveStore, DATA_EVENTS } from '../stores/live'
import { useToastStore } from '../stores/toast'
import { useQuery } from '../composables/useQuery'
import { useDateRange } from '../composables/useDateRange'
import { api, describeError } from '../lib/api'
import { displayCurrency, loadCurrency } from '../lib/currency'
import { daysBetween, num } from '../lib/format'
import type { Channel, RecommendationRequest } from '../lib/types'
import KpiRow from '../components/KpiRow.vue'
import DateRangePicker from '../components/DateRangePicker.vue'
import TrendChart from '../components/TrendChart.vue'
import ChannelMixChart from '../components/ChannelMixChart.vue'
import CampaignTable from '../components/CampaignTable.vue'
import BudgetPanel from '../components/BudgetPanel.vue'
import ErrorState from '../components/ErrorState.vue'
import Card from '../components/ui/Card.vue'
import Button from '../components/ui/Button.vue'
import EmptyState from '../components/ui/EmptyState.vue'

const ws = useWorkspaceStore()
const live = useLiveStore()
const toast = useToastStore()
const router = useRouter()
const key = computed(() => ws.key as string)
const slug = computed(() => ws.slug as string)
loadCurrency(slug.value)

const { range, preset, setPreset, set } = useDateRange(30)
const focus = ref<Channel | null>(null)
const days = computed(() => daysBetween(range.value.start, range.value.end))

const summary = useQuery((s) => api.summary(key.value, range.value, s), { deps: [range], refetchOn: DATA_EVENTS })
const mix = useQuery((s) => api.byChannel(key.value, range.value, s), { deps: [range], refetchOn: DATA_EVENTS })
const trend = useQuery((s) => api.trend(key.value, range.value, 'channel', s), { deps: [range], refetchOn: DATA_EVENTS })
const perf = useQuery((s) => api.campaignReport(key.value, range.value, null, s), { deps: [range], refetchOn: DATA_EVENTS })
const campaigns = useQuery((s) => api.campaigns(key.value, {}, s), { refetchOn: ['campaign.changed', 'import.completed'] })

const recReq = ref<RecommendationRequest>({ lookback_days: 30, min_share: 0.05, max_shift_pct: null, total_budget: null })
const rec = useQuery((s) => api.recommend(key.value, { ...recReq.value }, s), { deps: [recReq], refetchOn: ['metrics.upserted', 'import.completed'] })
function runRec(req: RecommendationRequest) {
  recReq.value = req
}

/** The workspace is empty when it has no metric rows at all (not just in this range). */
const workspaceEmpty = computed(() => {
  const st = ws.workspace?.stats
  if (st) return st.metric_rows === 0
  return false
})
const rangeEmpty = computed(() => !workspaceEmpty.value && !!summary.data.value && (summary.data.value.days_with_data ?? 0) === 0 && summary.data.value.spend === 0 && summary.data.value.impressions === 0)
const firstError = computed(() => summary.error.value ?? mix.error.value ?? trend.error.value ?? perf.error.value)
const anyLoading = computed(() => summary.loading.value || mix.loading.value || trend.loading.value || perf.loading.value)

function retryAll() {
  summary.run()
  mix.run()
  trend.run()
  perf.run()
  campaigns.run()
  rec.run()
}

const sampleBusy = ref(false)
async function loadSample() {
  sampleBusy.value = true
  try {
    const r = await api.importSample(key.value)
    toast.success(`Sample dataset imported`, `${num(r.summary?.rows_upserted ?? r.row_count)} rows · ${r.summary?.campaigns_created ?? 0} campaigns created`)
    live.touch('import.completed', { import_id: r.import_id })
    await ws.refresh()
    if (r.summary?.last_day && r.summary.first_day) set({ start: r.summary.first_day, end: r.summary.last_day })
  } catch (e) {
    toast.error('Sample import failed', describeError(e))
  } finally {
    sampleBusy.value = false
  }
}

// After a live import lands, surface it without flashing.
let lastToast = 0
live.on(['import.completed'], (e) => {
  const src = (e.data as { source?: string }).source
  if (src === 'local') return
  if (Date.now() - lastToast < 3000) return
  lastToast = Date.now()
  toast.info('New data arrived', 'Dashboard refreshed from the event stream.')
})
watch(focus, () => {
  /* focus just dims other series; no refetch */
})
</script>

<template>
  <div class="page">
    <header class="ph">
      <div>
        <h1>Dashboard</h1>
        <p class="muted sub" v-if="ws.workspace?.stats">
          <span class="num">{{ num(ws.workspace.stats.campaigns) }}</span> campaigns · <span class="num">{{ num(ws.workspace.stats.metric_rows) }}</span> daily rows
          <template v-if="ws.workspace.stats.first_day"> · data <span class="mono">{{ ws.workspace.stats.first_day }}</span> → <span class="mono">{{ ws.workspace.stats.last_day }}</span></template>
        </p>
      </div>
      <DateRangePicker :model-value="range" :preset="preset" @update:model-value="set" @preset="setPreset" />
    </header>

    <!-- Whole-workspace empty state -->
    <Card v-if="workspaceEmpty" class="emptycard">
      <EmptyState title="This workspace has no data yet" body="Import a Google Ads or Meta Ads CSV export, push rows through the REST endpoint, or load the attributed public sample dataset to see the dashboard work.">
        <template #mark><span class="mono">0</span></template>
        <template #actions>
          <Button variant="primary" :to="`/w/${slug}/import`">Import CSV</Button>
          <Button variant="secondary" :to="`/w/${slug}/import?tab=api`">Use the API</Button>
          <Button variant="ghost" :loading="sampleBusy" @click="loadSample">Load sample dataset</Button>
        </template>
      </EmptyState>
      <p class="muted attribution">The sample is a real public dataset (attributed on the Import page) — never loaded automatically.</p>
    </Card>

    <!-- Error (unreachable / server) -->
    <Card v-else-if="firstError && !anyLoading"><ErrorState :error="firstError" :retry="retryAll" /></Card>

    <template v-else>
      <KpiRow :report="summary.data.value" :loading="summary.loading.value" :currency="displayCurrency" />

      <Card v-if="rangeEmpty" class="rangeempty">
        <EmptyState compact title="No data in this date range" :body="`Your data covers ${ws.workspace?.stats?.first_day ?? '?'} to ${ws.workspace?.stats?.last_day ?? '?'}. Pick a range that overlaps it.`">
          <template #actions>
            <Button v-if="ws.workspace?.stats?.first_day && ws.workspace?.stats?.last_day" variant="primary" size="sm" @click="set({ start: ws.workspace!.stats!.first_day!, end: ws.workspace!.stats!.last_day! })">Jump to data</Button>
          </template>
        </EmptyState>
      </Card>

      <div class="charts">
        <TrendChart :report="trend.data.value" :loading="trend.loading.value" :currency="displayCurrency" :focus="focus" :delta-spend="summary.data.value?.delta_pct?.spend ?? null" @focus="focus = $event" />
        <ChannelMixChart :report="mix.data.value" :loading="mix.loading.value" :currency="displayCurrency" :focus="focus" @focus="focus = $event" />
      </div>

      <Card title="Campaigns" :subtitle="perf.data.value ? `${perf.data.value.length} with activity in range · click a row for daily detail` : undefined" flush>
        <CampaignTable
          :rows="perf.data.value ?? []"
          :campaigns="campaigns.data.value ?? []"
          :days="days"
          :loading="perf.loading.value"
          :currency="displayCurrency"
          :channel="focus"
          @update:channel="focus = $event"
          @open="(id) => router.push(`/w/${slug}/campaigns/${id}`)"
        />
      </Card>

      <BudgetPanel :result="rec.data.value" :loading="rec.loading.value" :error="rec.error.value" :currency="displayCurrency" :request="recReq" :has-data="!workspaceEmpty" @run="runRec" />
    </template>
  </div>
</template>

<style scoped>
.page { display: flex; flex-direction: column; gap: 18px; }
.ph { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; flex-wrap: wrap; }
.ph h1 { font-size: var(--fs-24); }
.sub { font-size: var(--fs-13); margin-top: 4px; }
.charts { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 16px; }
.emptycard :deep(.body) { padding: 32px 20px; }
.attribution { text-align: center; font-size: var(--fs-12); margin-top: 8px; }
@media (max-width: 1000px) { .charts { grid-template-columns: 1fr; } }
</style>
