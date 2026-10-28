<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useWorkspaceStore } from '../stores/workspace'
import { useToastStore } from '../stores/toast'
import { useLiveStore } from '../stores/live'
import { useQuery } from '../composables/useQuery'
import { api, ApiError, API_BASE, curlPreviewSnippet, curlSnippet, curlStreamSnippet, describeError } from '../lib/api'
import { displayCurrency, loadCurrency, setCurrency } from '../lib/currency'
import { longDate, num } from '../lib/format'
import type { Channel, ImportFormat, ImportResponse } from '../lib/types'
import Card from '../components/ui/Card.vue'
import Button from '../components/ui/Button.vue'
import Badge from '../components/ui/Badge.vue'
import Skeleton from '../components/ui/Skeleton.vue'
import CsvDropzone from '../components/CsvDropzone.vue'
import ImportPreview from '../components/ImportPreview.vue'
import CopyButton from '../components/CopyButton.vue'
import ErrorState from '../components/ErrorState.vue'

const ws = useWorkspaceStore()
const toast = useToastStore()
const live = useLiveStore()
const route = useRoute()
const router = useRouter()
const key = computed(() => ws.key as string)
const slug = computed(() => ws.slug as string)
loadCurrency(slug.value)

type Tab = 'csv' | 'api'
const tab = ref<Tab>(route.query.tab === 'api' ? 'api' : 'csv')
watch(tab, (t) => router.replace({ query: { ...route.query, tab: t === 'csv' ? undefined : t } }))

/* ---------- CSV flow ---------- */
const file = ref<File | null>(null)
const preview = ref<ImportResponse | null>(null)
const previewError = ref<ApiError | null>(null)
const analysing = ref(false)
const committing = ref(false)
const format = ref<ImportFormat | null>(null)
const channel = ref<Channel | null>(null)

async function analyse() {
  if (!file.value) return
  analysing.value = true
  previewError.value = null
  try {
    preview.value = await api.importCsv(key.value, file.value, { dryRun: true, format: format.value, channel: channel.value })
    if (preview.value.currency && displayCurrency.value === 'USD' && preview.value.currency !== 'USD') {
      setCurrency(preview.value.currency)
      toast.info(`Display currency set to ${preview.value.currency}`, 'Detected from the export. Change it in Settings.')
    }
  } catch (e) {
    preview.value = null
    previewError.value = e instanceof ApiError ? e : new ApiError('server', 0, describeError(e))
  } finally {
    analysing.value = false
  }
}
function onFile(f: File) {
  file.value = f
  preview.value = null
  format.value = null
  channel.value = null
  void analyse()
}
function reset() {
  file.value = null
  preview.value = null
  previewError.value = null
}
watch([format, channel], () => {
  if (file.value && preview.value) void analyse()
})

async function commit() {
  if (!file.value) return
  committing.value = true
  try {
    const r = await api.importCsv(key.value, file.value, { dryRun: false, format: format.value, channel: channel.value })
    const s = r.summary
    toast.success(`Imported ${num(s?.rows_upserted ?? r.row_count)} rows`, s ? `${s.campaigns_created} new campaigns · ${s.first_day} → ${s.last_day}` : undefined)
    live.touch('import.completed', { import_id: r.import_id })
    await ws.refresh()
    const q = s?.first_day && s.last_day ? { start: s.first_day, end: s.last_day } : {}
    router.push({ path: `/w/${slug.value}`, query: q })
  } catch (e) {
    toast.error('Import failed', describeError(e))
  } finally {
    committing.value = false
  }
}

/* ---------- sample dataset ---------- */
const sample = useQuery((s) => api.sampleInfo(s))
const sampleBusy = ref(false)
async function loadSample() {
  sampleBusy.value = true
  try {
    const r = await api.importSample(key.value)
    toast.success('Sample dataset imported', `${num(r.summary?.rows_upserted ?? r.row_count)} rows · ${r.summary?.campaigns_created ?? 0} campaigns created`)
    live.touch('import.completed', { import_id: r.import_id })
    await ws.refresh()
    const s = r.summary
    router.push({ path: `/w/${slug.value}`, query: s?.first_day && s.last_day ? { start: s.first_day, end: s.last_day } : {} })
  } catch (e) {
    toast.error('Sample import failed', describeError(e))
  } finally {
    sampleBusy.value = false
  }
}

/* ---------- history ---------- */
const history = useQuery((s) => api.imports(key.value, 10, s), { refetchOn: ['import.completed', 'metrics.upserted'] })
const sourceLabel: Record<string, string> = { google_ads: 'Google Ads CSV', meta_ads: 'Meta Ads CSV', generic: 'Generic CSV', api: 'REST API', sample: 'Sample dataset' }

/* ---------- API tab ---------- */
const revealed = ref(false)
const shownKey = computed(() => (revealed.value ? key.value : `${key.value.slice(0, 8)}${'•'.repeat(12)}${key.value.slice(-4)}`))
const snippetBulk = computed(() => curlSnippet(shownKey.value))
const snippetPreview = computed(() => curlPreviewSnippet(shownKey.value))
const snippetStream = computed(() => curlStreamSnippet(shownKey.value))
</script>

<template>
  <div class="page">
    <header class="ph">
      <div>
        <h1>Import data</h1>
        <p class="muted sub">Bring real spend in three ways. Every import is idempotent: rows upsert on (channel, campaign, day).</p>
      </div>
      <div class="tabs" role="tablist" aria-label="Import method">
        <button role="tab" type="button" :aria-selected="tab === 'csv'" :class="{ on: tab === 'csv' }" @click="tab = 'csv'">CSV upload</button>
        <button role="tab" type="button" :aria-selected="tab === 'api'" :class="{ on: tab === 'api' }" @click="tab = 'api'">API ingest</button>
      </div>
    </header>

    <!-- CSV -->
    <div v-if="tab === 'csv'" class="stack gap-4" role="tabpanel">
      <Card title="Upload a CSV export" subtitle="Google Ads (Campaign, Cost, Impressions, Clicks, Conversions, Day) · Meta Ads Manager (Campaign name, Amount spent, Impressions, Link clicks, Results, Day) · generic template">
        <template #actions>
          <a class="tmpl" :href="`data:text/csv;charset=utf-8,${encodeURIComponent('day,channel,campaign,external_id,impressions,clicks,conversions,spend,revenue\n')}`" download="channelmix-template.csv">Download generic template</a>
        </template>
        <CsvDropzone :file="file" :busy="analysing" @file="onFile" />
        <div v-if="analysing" class="analysing" aria-busy="true">
          <Skeleton width="180px" height="14px" /><Skeleton width="100%" height="120px" radius="10px" />
        </div>
        <ErrorState v-else-if="previewError" compact :error="previewError" :title="previewError.kind === 'validation' ? 'We couldn’t parse that file' : undefined" :retry="analyse" />
        <div v-else-if="preview" class="previewwrap">
          <ImportPreview :preview="preview" :file-name="file?.name ?? ''" :committing="committing" v-model:format="format" v-model:channel="channel" :currency="displayCurrency" @commit="commit" @cancel="reset" />
        </div>
      </Card>

      <Card title="Load sample dataset" subtitle="Real public data, attributed — imported into this workspace only when you click.">
        <div v-if="sample.loading.value" class="stack gap-2"><Skeleton width="60%" /><Skeleton width="40%" /></div>
        <ErrorState v-else-if="sample.error.value" compact :error="sample.error.value" :retry="sample.run" />
        <div v-else-if="sample.data.value" class="sample">
          <div class="sinfo">
            <div class="strong">{{ sample.data.value.name }}</div>
            <p class="muted desc">{{ sample.data.value.description }}</p>
            <p class="meta">
              <span class="num">{{ num(sample.data.value.rows) }}</span> rows · {{ sample.data.value.channels.join(', ') }}
              <template v-if="sample.data.value.first_day"> · <span class="mono">{{ sample.data.value.first_day }}</span> → <span class="mono">{{ sample.data.value.last_day }}</span></template>
            </p>
            <p class="muted attribution">
              Source: <a class="lnk" :href="sample.data.value.source_url" target="_blank" rel="noreferrer">{{ sample.data.value.attribution }}</a> · {{ sample.data.value.license }}
            </p>
          </div>
          <Button variant="secondary" :loading="sampleBusy" @click="loadSample">Load sample dataset</Button>
        </div>
      </Card>
    </div>

    <!-- API -->
    <div v-else class="stack gap-4" role="tabpanel">
      <Card title="Push rows with one request" subtitle="Campaigns are created on the fly from channel + external_id. Add an Idempotency-Key header to make retries safe.">
        <template #actions>
          <Button size="sm" variant="ghost" :aria-pressed="revealed" @click="revealed = !revealed">{{ revealed ? 'Hide key' : 'Reveal key' }}</Button>
          <CopyButton :text="curlSnippet(key)" label="Copy curl" />
        </template>
        <pre class="code" tabindex="0" aria-label="curl command to push metrics"><code>{{ snippetBulk }}</code></pre>
        <div class="endpoints">
          <div class="ep"><Badge tone="accent" mono size="sm">POST</Badge><code class="mono">{{ API_BASE }}/metrics/bulk</code><span class="muted">upsert daily rows (1–100k per call)</span></div>
          <div class="ep"><Badge tone="neutral" mono size="sm">POST</Badge><code class="mono">{{ API_BASE }}/imports/csv</code><span class="muted">multipart CSV, <span class="mono">dry_run=true</span> previews</span></div>
          <div class="ep"><Badge tone="neutral" mono size="sm">GET</Badge><code class="mono">{{ API_BASE }}/stream</code><span class="muted">server-sent events as data lands</span></div>
          <div class="ep"><Badge tone="neutral" mono size="sm">GET</Badge><code class="mono">{{ API_BASE.replace('/api/v1', '') }}/docs</code><span class="muted">OpenAPI reference</span></div>
        </div>
      </Card>
      <div class="two">
        <Card title="Preview a CSV from the terminal">
          <template #actions><CopyButton :text="curlPreviewSnippet(key)" label="Copy" /></template>
          <pre class="code" tabindex="0"><code>{{ snippetPreview }}</code></pre>
        </Card>
        <Card title="Follow the event stream">
          <template #actions><CopyButton :text="curlStreamSnippet(key)" label="Copy" /></template>
          <pre class="code" tabindex="0"><code>{{ snippetStream }}</code></pre>
        </Card>
      </div>
      <p class="muted note">Header <span class="mono">X-Api-Key</span> scopes every call to this workspace. Rotate the key in Settings if it leaks.</p>
    </div>

    <!-- History -->
    <Card title="Recent imports" flush>
      <div v-if="history.loading.value" class="hist-sk"><Skeleton v-for="i in 3" :key="i" height="40px" radius="0" /></div>
      <ErrorState v-else-if="history.error.value" compact :error="history.error.value" :retry="history.run" />
      <ul v-else-if="history.data.value?.length" class="hist">
        <li v-for="h in history.data.value" :key="h.id" class="hrow">
          <span class="mono id">#{{ h.id }}</span>
          <span class="src">{{ sourceLabel[h.source] ?? h.source }}<span v-if="h.filename" class="muted"> · <span class="mono">{{ h.filename }}</span></span></span>
          <span class="num cnt">{{ num(h.rows_upserted) }} rows<span v-if="h.campaigns_created" class="muted"> · {{ h.campaigns_created }} new</span></span>
          <Badge :tone="h.status === 'completed' ? 'success' : h.status === 'failed' ? 'error' : 'neutral'" size="sm">{{ h.status }}</Badge>
          <span class="muted when">{{ longDate(h.created_at) }}</span>
          <span v-if="h.warnings?.length" class="muted warn" :title="h.warnings.join('\n')">{{ h.warnings.length }} warning{{ h.warnings.length > 1 ? 's' : '' }}</span>
        </li>
      </ul>
      <p v-else class="muted none">No imports yet.</p>
    </Card>
  </div>
</template>

<style scoped>
.page { display: flex; flex-direction: column; gap: 18px; }
.ph { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; flex-wrap: wrap; }
.ph h1 { font-size: var(--fs-24); }
.sub { font-size: var(--fs-13); margin-top: 4px; max-width: 60ch; }
.tabs { display: inline-flex; border: 1px solid var(--border); border-radius: var(--r-md); overflow: hidden; background: var(--surface-2); }
.tabs button { height: 34px; padding: 0 14px; border: 0; background: transparent; color: var(--muted); font-size: var(--fs-13); font-weight: 500; }
.tabs button + button { border-left: 1px solid var(--border); }
.tabs button.on { background: var(--surface-3); color: var(--text-strong); box-shadow: inset 0 -2px 0 var(--accent); }
.tabs button:focus-visible { box-shadow: inset var(--ring); border-radius: 0; }
.tmpl { font-size: var(--fs-13); color: var(--accent); white-space: nowrap; }
.tmpl:hover { text-decoration: underline; }
.analysing { display: flex; flex-direction: column; gap: 10px; margin-top: 16px; }
.previewwrap { margin-top: 20px; }
.sample { display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap; }
.sinfo { display: flex; flex-direction: column; gap: 4px; min-width: 0; max-width: 70ch; }
.desc { font-size: var(--fs-13); line-height: 1.5; }
.meta { font-size: var(--fs-13); }
.attribution { font-size: var(--fs-12); }
.lnk { color: var(--text); text-decoration: underline; text-decoration-color: var(--border-strong); text-underline-offset: 2px; }
.lnk:hover { color: var(--text-strong); text-decoration-color: var(--text-strong); }
.code { background: var(--bg); border: 1px solid var(--border); border-radius: var(--r-md); padding: 12px 14px; font-size: var(--fs-13); line-height: 1.55; overflow-x: auto; color: var(--text); }
.code:focus-visible { box-shadow: var(--ring); }
.endpoints { display: flex; flex-direction: column; gap: 8px; margin-top: 14px; }
.ep { display: grid; grid-template-columns: auto auto 1fr; gap: 10px; align-items: center; font-size: var(--fs-13); }
.ep code { color: var(--text-strong); overflow-wrap: anywhere; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.note { font-size: var(--fs-13); }
.hist { display: flex; flex-direction: column; }
.hrow { display: grid; grid-template-columns: 56px minmax(140px, 2fr) minmax(110px, 1fr) auto auto auto; gap: 12px; align-items: center; padding: 10px 20px; border-top: 1px solid var(--border); font-size: var(--fs-13); }
.hrow:first-child { border-top: 0; }
.id { color: var(--muted); }
.src { color: var(--text-strong); min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.when { white-space: nowrap; }
.hist-sk { display: flex; flex-direction: column; gap: 1px; }
.none { padding: 20px; font-size: var(--fs-13); }
@media (max-width: 900px) { .two { grid-template-columns: 1fr; } .hrow { grid-template-columns: 48px 1fr auto; } .cnt, .when, .warn { display: none; } .ep { grid-template-columns: auto 1fr; } .ep .muted { grid-column: 1 / -1; } }
</style>
