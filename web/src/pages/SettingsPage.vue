<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useWorkspaceStore } from '../stores/workspace'
import { useToastStore } from '../stores/toast'
import { useLiveStore } from '../stores/live'
import { api, ApiError, API_URL, describeError } from '../lib/api'
import { CURRENCIES, displayCurrency, loadCurrency, setCurrency } from '../lib/currency'
import { longDate, num } from '../lib/format'
import Card from '../components/ui/Card.vue'
import Button from '../components/ui/Button.vue'
import Input from '../components/ui/Input.vue'
import Select from '../components/ui/Select.vue'
import Dialog from '../components/ui/Dialog.vue'
import Badge from '../components/ui/Badge.vue'
import CopyButton from '../components/CopyButton.vue'

const ws = useWorkspaceStore()
const toast = useToastStore()
const live = useLiveStore()
const router = useRouter()
const key = computed(() => ws.key as string)
const slug = computed(() => ws.slug as string)
loadCurrency(slug.value)

const revealed = ref(false)
const masked = computed(() => `${key.value.slice(0, 8)}${'•'.repeat(16)}${key.value.slice(-4)}`)
const magic = computed(() => `${location.origin}/w/${slug.value}?key=${key.value}`)

/* rotate */
const rotateOpen = ref(false)
const rotating = ref(false)
async function rotate() {
  rotating.value = true
  try {
    await ws.rotate()
    rotateOpen.value = false
    toast.success('Key rotated', 'The old key stops working immediately.')
  } catch (e) {
    const msg = e instanceof ApiError && (e.status === 404 || e.status === 405) ? 'Key rotation is not available on this API version yet.' : describeError(e)
    toast.error('Could not rotate key', msg)
  } finally {
    rotating.value = false
  }
}

/* danger: clear data */
const clearOpen = ref(false)
const clearConfirm = ref('')
const clearing = ref(false)
const clearProgress = ref<string | null>(null)
async function clearData() {
  clearing.value = true
  try {
    const camps = await api.campaigns(key.value)
    let done = 0
    for (const c of camps) {
      await api.deleteCampaign(key.value, c.id)
      done += 1
      clearProgress.value = `${done} / ${camps.length}`
    }
    toast.success(`Deleted ${camps.length} campaigns and their metrics`)
    live.touch('campaign.changed', { action: 'deleted' })
    await ws.refresh()
    clearOpen.value = false
    clearConfirm.value = ''
  } catch (e) {
    toast.error('Could not delete everything', describeError(e))
  } finally {
    clearing.value = false
    clearProgress.value = null
  }
}

/* danger: delete workspace */
const deleteOpen = ref(false)
const deleteConfirm = ref('')
const deleting = ref(false)
async function destroy() {
  deleting.value = true
  try {
    await ws.destroy()
    toast.success('Workspace deleted')
    router.push('/')
  } catch (e) {
    const msg = e instanceof ApiError && (e.status === 404 || e.status === 405) ? 'Workspace deletion is not available on this API version yet. You can clear all data instead.' : describeError(e)
    toast.error('Could not delete workspace', msg)
  } finally {
    deleting.value = false
  }
}

function forget() {
  ws.signOut()
  toast.info('Key removed from this browser')
  router.push('/')
}
</script>

<template>
  <div class="page">
    <header class="ph"><h1>Settings</h1></header>

    <div class="grid">
      <Card title="Workspace">
        <dl class="dl" v-if="ws.workspace">
          <dt>Name</dt><dd class="strong">{{ ws.workspace.name }}</dd>
          <dt>Slug</dt><dd class="mono">{{ ws.workspace.slug }}</dd>
          <dt>Email</dt><dd>{{ ws.workspace.email ?? '–' }}</dd>
          <dt>Created</dt><dd>{{ longDate(ws.workspace.created_at) }}</dd>
          <dt>Workspace id</dt><dd class="mono">{{ ws.workspace.id }}</dd>
          <template v-if="ws.workspace.stats">
            <dt>Data</dt>
            <dd class="num">{{ num(ws.workspace.stats.campaigns) }} campaigns · {{ num(ws.workspace.stats.metric_rows) }} daily rows · {{ num(ws.workspace.stats.imports) }} imports<template v-if="ws.workspace.stats.first_day"><br /><span class="mono">{{ ws.workspace.stats.first_day }}</span> → <span class="mono">{{ ws.workspace.stats.last_day }}</span></template></dd>
          </template>
          <dt>API</dt><dd class="mono small">{{ API_URL }}</dd>
        </dl>
      </Card>

      <Card title="Display" subtitle="Formatting only — the API stores plain amounts in whatever currency you imported.">
        <div class="row gap-3 wrap">
          <Select :model-value="displayCurrency" label="Currency" :options="CURRENCIES.map((c) => ({ value: c, label: c }))" @update:model-value="setCurrency" />
          <Input :model-value="displayCurrency" label="Or any ISO code" placeholder="e.g. CHF" mono style="width: 140px" @update:model-value="(v) => v.length === 3 && setCurrency(v)" />
        </div>
      </Card>
    </div>

    <Card title="API key" subtitle="Scopes every request to this workspace. Stored hashed on the server; this browser keeps a copy in localStorage.">
      <div class="keyrow">
        <code class="mono keybox" data-testid="key">{{ revealed ? key : masked }}</code>
        <Button size="sm" variant="ghost" :aria-pressed="revealed" @click="revealed = !revealed">{{ revealed ? 'Hide' : 'Reveal' }}</Button>
        <CopyButton :text="key" label="Copy key" />
        <CopyButton :text="magic" label="Copy magic link" />
      </div>
      <div class="actions">
        <Button variant="secondary" @click="rotateOpen = true">Rotate key…</Button>
        <Button variant="ghost" @click="forget">Forget key on this device</Button>
      </div>
    </Card>

    <Card title="Danger zone" class="danger">
      <div class="drow">
        <div><div class="strong">Delete all campaigns and metrics</div><p class="muted">Removes every campaign (and its daily rows) in this workspace. The workspace and key stay.</p></div>
        <Button variant="danger" @click="clearOpen = true">Clear data…</Button>
      </div>
      <div class="drow">
        <div><div class="strong">Delete workspace</div><p class="muted">Deletes the workspace, its key and all data. There is no undo.</p></div>
        <Button variant="danger" @click="deleteOpen = true">Delete workspace…</Button>
      </div>
    </Card>

    <Dialog :open="rotateOpen" title="Rotate the API key?" description="A new key is generated and shown once. The current key stops working immediately — update any scripts that push data." @close="rotateOpen = false">
      <Badge tone="warning">Scripts using the old key will get 401</Badge>
      <template #footer>
        <Button variant="ghost" @click="rotateOpen = false">Cancel</Button>
        <Button variant="primary" :loading="rotating" @click="rotate">Rotate key</Button>
      </template>
    </Dialog>

    <Dialog :open="clearOpen" title="Delete all data?" :description="`Type the workspace slug to confirm. ${ws.workspace?.stats ? num(ws.workspace.stats.campaigns) + ' campaigns and ' + num(ws.workspace.stats.metric_rows) + ' rows will be deleted.' : ''}`" @close="!clearing && (clearOpen = false)">
      <Input v-model="clearConfirm" mono :placeholder="slug" aria-label="Type the workspace slug to confirm" />
      <p v-if="clearProgress" class="muted progress num">Deleting… {{ clearProgress }}</p>
      <template #footer>
        <Button variant="ghost" :disabled="clearing" @click="clearOpen = false">Cancel</Button>
        <Button variant="danger" :disabled="clearConfirm !== slug" :loading="clearing" @click="clearData">Delete everything</Button>
      </template>
    </Dialog>

    <Dialog :open="deleteOpen" title="Delete this workspace?" description="Type the workspace slug to confirm. The key, campaigns, metrics and import history are removed permanently." @close="!deleting && (deleteOpen = false)">
      <Input v-model="deleteConfirm" mono :placeholder="slug" aria-label="Type the workspace slug to confirm" />
      <template #footer>
        <Button variant="ghost" :disabled="deleting" @click="deleteOpen = false">Cancel</Button>
        <Button variant="danger" :disabled="deleteConfirm !== slug" :loading="deleting" @click="destroy">Delete workspace</Button>
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.page { display: flex; flex-direction: column; gap: 18px; max-width: 980px; }
.ph h1 { font-size: var(--fs-24); }
.grid { display: grid; grid-template-columns: 3fr 2fr; gap: 16px; }
.dl { display: grid; grid-template-columns: 120px 1fr; gap: 10px 16px; font-size: var(--fs-14); margin: 0; }
.dl dt { color: var(--muted); font-size: var(--fs-13); }
.dl dd { margin: 0; min-width: 0; overflow-wrap: anywhere; }
.small { font-size: var(--fs-13); }
.keyrow { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.keybox { flex: 1 1 320px; min-width: 0; padding: 8px 12px; background: var(--bg); border: 1px solid var(--border); border-radius: var(--r-md); font-size: var(--fs-13); color: var(--text-strong); overflow-wrap: anywhere; }
.actions { display: flex; gap: 8px; margin-top: 14px; flex-wrap: wrap; }
.danger { border-color: rgba(209, 99, 167, 0.4); }
.drow { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 12px 0; border-top: 1px solid var(--border); flex-wrap: wrap; }
.drow:first-child { border-top: 0; padding-top: 0; }
.drow p { font-size: var(--fs-13); margin-top: 2px; max-width: 60ch; }
.progress { margin-top: 10px; font-size: var(--fs-13); }
@media (max-width: 900px) { .grid { grid-template-columns: 1fr; } .dl { grid-template-columns: 100px 1fr; } }
</style>
