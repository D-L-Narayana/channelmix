<script setup lang="ts">
/**
 * Product page: one sentence of value, the real app shell as the live preview (empty-workspace
 * state, real API health), create-workspace form and open-existing key input. No fake numbers.
 */
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useWorkspaceStore, lastSlug, storedKey } from '../stores/workspace'
import { useToastStore } from '../stores/toast'
import { useQuery } from '../composables/useQuery'
import { api, API_URL, describeError } from '../lib/api'
import type { SummaryReport } from '../lib/types'
import Wordmark from '../components/Wordmark.vue'
import Button from '../components/ui/Button.vue'
import Input from '../components/ui/Input.vue'
import Card from '../components/ui/Card.vue'
import Badge from '../components/ui/Badge.vue'
import EmptyState from '../components/ui/EmptyState.vue'
import KpiRow from '../components/KpiRow.vue'
import FreshKeyDialog from '../components/FreshKeyDialog.vue'

const ws = useWorkspaceStore()
const toast = useToastStore()
const router = useRouter()

const health = useQuery((s) => api.health(s))
const apiHost = API_URL.replace(/^https?:\/\//, '')

/* create */
const name = ref('')
const email = ref('')
const creating = ref(false)
const createError = ref<string | null>(null)
const createdSlug = ref<string | null>(null)
async function create() {
  createError.value = null
  if (name.value.trim().length < 1) return (createError.value = 'Give the workspace a name.')
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.value)) return (createError.value = 'Enter a valid email address.')
  creating.value = true
  try {
    const created = await ws.create(name.value.trim(), email.value.trim())
    createdSlug.value = created.slug
    // FreshKeyDialog shows the key once; navigate when it is dismissed (see watcher below)
  } catch (e) {
    createError.value = describeError(e)
  } finally {
    creating.value = false
  }
}
const unwatch = ws.$subscribe(() => {
  if (createdSlug.value && !ws.freshKey) {
    const s = createdSlug.value
    createdSlug.value = null
    unwatch()
    router.push(`/w/${s}`)
  }
})

/* open existing */
const openSlug = ref(lastSlug() ?? '')
const openKey = ref('')
const opening = ref(false)
const openError = ref<string | null>(null)
const remembered = computed(() => (openSlug.value && storedKey(openSlug.value) ? true : false))
async function open() {
  openError.value = null
  const s = openSlug.value.trim().toLowerCase().replace(/^.*\/w\//, '').split(/[?#]/)[0]
  if (!/^[a-z0-9-]+$/.test(s)) return (openError.value = 'Enter the workspace slug (e.g. acme-retail-k3f9) or paste its URL.')
  const k = openKey.value.trim()
  if (!k && !storedKey(s)) return (openError.value = 'Paste the workspace key (starts with cmx_).')
  opening.value = true
  if (k) await ws.useKey(s, k)
  else await ws.open(s)
  opening.value = false
  if (ws.state === 'ready') router.push(`/w/${s}`)
  else if (ws.state === 'unreachable') toast.error('API unreachable', ws.error ?? undefined)
  else openError.value = ws.error ?? 'That key was rejected.'
}

/* preview: what a brand-new workspace looks like (zeros, not fakes) */
const zeroSummary: SummaryReport = {
  start: new Date(Date.now() - 29 * 864e5).toISOString().slice(0, 10),
  end: new Date().toISOString().slice(0, 10),
  spend: 0, revenue: 0, impressions: 0, clicks: 0, conversions: 0, roas: null, cpa: null, ctr: null, cpc: null,
  days_with_data: 0, campaigns: 0, previous: null, delta_pct: {},
}
</script>

<template>
  <div class="landing">
    <header class="top">
      <Wordmark size="md" />
      <nav class="links" aria-label="Primary">
        <a :href="`${API_URL}/docs`" target="_blank" rel="noreferrer">API docs</a>
        <a href="https://github.com/D-L-Narayana/channelmix" target="_blank" rel="noreferrer">Source</a>
      </nav>
    </header>

    <main id="main" class="hero" tabindex="-1">
      <div class="copy">
        <h1>One live view of ad spend across Google, Meta and Amazon — with a budget split that pays back more.</h1>
        <p class="lead">Create a workspace, import your real exports or push rows through the API, and watch spend, ROAS and the recommended reallocation update as data lands.</p>
        <ul class="steps" aria-label="How it works">
          <li><span class="n mono">1</span><span>Create a workspace — name + email, no password. You get an API key once.</span></li>
          <li><span class="n mono">2</span><span>Drop a Google Ads or Meta Ads CSV, or <span class="mono">POST /metrics/bulk</span>. Preview the mapping before anything is written.</span></li>
          <li><span class="n mono">3</span><span>The dashboard streams updates over SSE; recommendations use your own response curves.</span></li>
        </ul>
        <p class="status">
          <template v-if="health.loading.value"><Badge tone="neutral" dot>Checking API…</Badge></template>
          <template v-else-if="health.data.value"><Badge tone="success" dot>API online</Badge> <span class="mono muted small">{{ apiHost }} · v{{ health.data.value.version ?? '?' }}<template v-if="health.data.value.database"> · {{ health.data.value.database }}</template></span></template>
          <template v-else><Badge tone="error" dot>API unreachable</Badge> <span class="mono muted small">{{ apiHost }}</span> <button class="retry" type="button" @click="health.run">Retry</button></template>
        </p>
      </div>

      <div class="forms">
        <Card title="Create a workspace" subtitle="Takes one step. Your data is isolated by the key you receive.">
          <form class="form" @submit.prevent="create" novalidate>
            <Input v-model="name" label="Workspace name" placeholder="Acme Retail" required autocomplete="organization" name="name" />
            <Input v-model="email" type="email" label="Email" placeholder="you@company.com" required autocomplete="email" name="email" hint="Only used to label the workspace. No password, no verification mail." />
            <p v-if="createError" class="err" role="alert">{{ createError }}</p>
            <Button type="submit" variant="primary" size="lg" block :loading="creating" :disabled="health.error.value !== null && !health.loading.value">Create workspace</Button>
          </form>
        </Card>
        <Card title="Open an existing workspace" :subtitle="remembered ? 'A key for this workspace is saved in this browser.' : 'Paste the slug (or URL) and key you were given.'">
          <form class="form" @submit.prevent="open" novalidate>
            <Input v-model="openSlug" label="Workspace slug or URL" placeholder="acme-retail-k3f9" mono autocomplete="off" name="slug" />
            <Input v-model="openKey" label="Workspace key" :placeholder="remembered ? 'saved in this browser' : 'cmx_…'" mono autocomplete="off" name="key" />
            <p v-if="openError" class="err" role="alert">{{ openError }}</p>
            <Button type="submit" variant="secondary" block :loading="opening">Open workspace</Button>
          </form>
        </Card>
      </div>
    </main>

    <!-- Live product preview: the real shell in its brand-new state -->
    <section class="preview" aria-label="Product preview">
      <div class="pv-head">
        <span class="eyebrow">What you get</span>
        <span class="muted small">This is the real dashboard shell in the state a new workspace starts in — nothing below is simulated.</span>
      </div>
      <div class="frame" inert>
        <div class="fake-top">
          <div class="left"><Wordmark size="sm" /><span class="sep">/</span><span class="wsn">Your workspace</span></div>
          <div class="nav"><span class="on">Dashboard</span><span>Import</span><span>Settings</span></div>
          <div class="right"><span class="live"><i /> Live updates connect here</span></div>
        </div>
        <div class="frame-body">
          <div class="frame-ph">
            <h2>Dashboard</h2>
            <div class="presets"><span>7d</span><span>14d</span><span class="on">30d</span><span>90d</span><span>Custom</span></div>
          </div>
          <KpiRow :report="zeroSummary" currency="USD" />
          <Card>
            <EmptyState title="This workspace has no data yet" body="Import a Google Ads or Meta Ads CSV export, push rows through the REST endpoint, or load the attributed public sample dataset to see the dashboard work.">
              <template #mark><span class="mono">0</span></template>
              <template #actions>
                <Button variant="primary">Import CSV</Button>
                <Button variant="secondary">Use the API</Button>
                <Button variant="ghost">Load sample dataset</Button>
              </template>
            </EmptyState>
          </Card>
        </div>
      </div>
    </section>

    <footer class="foot">
      <span>FastAPI · PostgreSQL · Vue 3 · ECharts · server-sent events</span>
      <span class="muted">Workspace keys are stored hashed. No tracking, no cookies.</span>
    </footer>

    <FreshKeyDialog />
  </div>
</template>

<style scoped>
.landing { max-width: var(--content-max); margin: 0 auto; padding: 0 24px 48px; }
.top { height: 64px; display: flex; justify-content: space-between; align-items: center; }
.links { display: flex; gap: 20px; font-size: var(--fs-14); color: var(--muted); }
.links a:hover { color: var(--text-strong); }
.hero { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(320px, 440px); gap: 48px; align-items: start; padding: 56px 0 40px; outline: none; }
.copy { display: flex; flex-direction: column; gap: 20px; max-width: 640px; }
h1 { font-size: clamp(1.75rem, 3.2vw, 2.75rem); font-weight: 500; letter-spacing: -0.025em; line-height: 1.12; text-wrap: balance; }
.lead { font-size: var(--fs-18); line-height: 1.5; color: var(--text); max-width: 56ch; }
.steps { display: flex; flex-direction: column; gap: 10px; margin-top: 4px; font-size: var(--fs-14); color: var(--text); }
.steps li { display: flex; gap: 12px; align-items: baseline; line-height: 1.5; }
.steps .n { flex-shrink: 0; width: 22px; height: 22px; display: inline-grid; place-items: center; border: 1px solid var(--border-strong); border-radius: 50%; font-size: var(--fs-12); color: var(--muted); transform: translateY(2px); }
.status { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 6px; }
.small { font-size: var(--fs-12); }
.retry { background: none; border: 0; color: var(--accent); font-size: var(--fs-13); padding: 0 4px; }
.forms { display: flex; flex-direction: column; gap: 16px; }
.form { display: flex; flex-direction: column; gap: 14px; }
.err { color: var(--error); font-size: var(--fs-13); }

.preview { margin-top: 24px; }
.pv-head { display: flex; gap: 14px; align-items: baseline; flex-wrap: wrap; margin-bottom: 12px; }
.frame { border: 1px solid var(--border); border-radius: var(--r-lg); overflow: hidden; background: var(--bg); box-shadow: var(--shadow-2); }
.fake-top { height: 52px; display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; padding: 0 20px; border-bottom: 1px solid var(--border); background: var(--surface); font-size: var(--fs-14); }
.fake-top .left { display: flex; align-items: center; gap: 10px; }
.sep { color: var(--faint); }
.wsn { color: var(--text-strong); font-weight: 500; }
.fake-top .nav { display: flex; gap: 24px; color: var(--muted); }
.fake-top .nav .on { color: var(--text-strong); box-shadow: 0 2px 0 var(--accent); padding-bottom: 14px; margin-bottom: -16px; }
.fake-top .right { display: flex; justify-content: flex-end; }
.live { display: inline-flex; align-items: center; gap: 7px; font-size: var(--fs-12); color: var(--text); border: 1px solid var(--border); border-radius: var(--r-pill); padding: 0 8px; height: 24px; background: var(--surface-2); }
.live i { width: 7px; height: 7px; border-radius: 50%; background: var(--faint); }
.frame-body { padding: 20px; display: flex; flex-direction: column; gap: 16px; }
.frame-ph { display: flex; justify-content: space-between; align-items: center; }
.frame-ph h2 { font-size: var(--fs-20); }
.presets { display: inline-flex; border: 1px solid var(--border); border-radius: var(--r-md); overflow: hidden; background: var(--surface-2); font-size: var(--fs-13); color: var(--muted); }
.presets span { padding: 0 12px; height: 32px; display: inline-flex; align-items: center; }
.presets span + span { border-left: 1px solid var(--border); }
.presets .on { color: var(--text-strong); background: var(--surface-3); box-shadow: inset 0 -2px 0 var(--accent); }
.foot { display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-top: 40px; padding-top: 20px; border-top: 1px solid var(--border); font-size: var(--fs-13); color: var(--muted); }

@media (max-width: 1000px) { .hero { grid-template-columns: 1fr; gap: 32px; padding-top: 36px; } .forms { max-width: 520px; } }
@media (max-width: 640px) {
  .landing { padding: 0 16px 32px; }
  .hero { padding-top: 24px; }
  .lead { font-size: var(--fs-16); }
  .fake-top { grid-template-columns: 1fr auto; padding: 0 14px; }
  .fake-top .nav { display: none; }
  .frame-body { padding: 14px; }
  .presets span { padding: 0 8px; }
}
</style>
