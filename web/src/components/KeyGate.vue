<script setup lang="ts">
/** Designed states for a /w/:slug route when the key is missing, invalid, or the API is unreachable. */
import { ref } from 'vue'
import { useWorkspaceStore } from '../stores/workspace'
import { API_URL } from '../lib/api'
import Button from './ui/Button.vue'
import Input from './ui/Input.vue'
import Wordmark from './Wordmark.vue'

const props = defineProps<{ slug: string }>()
const ws = useWorkspaceStore()
const pasted = ref('')
const busy = ref(false)
const keyError = ref<string | null>(null)

async function submit() {
  const k = pasted.value.trim()
  if (!k) {
    keyError.value = 'Paste the workspace key (starts with cmx_).'
    return
  }
  keyError.value = null
  busy.value = true
  await ws.useKey(props.slug, k)
  busy.value = false
  if (ws.state === 'invalid') keyError.value = ws.error ?? 'That key was rejected.'
}
async function retry() {
  busy.value = true
  await ws.retry()
  busy.value = false
}
</script>

<template>
  <div class="gate">
    <div class="box" role="region" :aria-label="ws.state === 'unreachable' ? 'API unreachable' : 'Workspace key required'">
      <Wordmark size="md" />

      <template v-if="ws.state === 'unreachable'">
        <p class="eyebrow err">API unreachable</p>
        <h1>We can't reach the ChannelMix API.</h1>
        <p class="muted lead">
          The dashboard talks to <code class="mono">{{ API_URL }}</code>. It didn't answer, so nothing is shown — ChannelMix never substitutes
          placeholder data.
        </p>
        <p v-if="ws.error" class="detail mono">{{ ws.error }}</p>
        <div class="actions">
          <Button variant="primary" :loading="busy" @click="retry">Retry</Button>
          <Button variant="ghost" to="/">Back to start</Button>
        </div>
      </template>

      <template v-else>
        <p class="eyebrow" :class="{ err: ws.state === 'invalid' }">{{ ws.state === 'invalid' ? 'Key rejected' : 'Key required' }}</p>
        <h1 v-if="ws.state === 'invalid'">This workspace key doesn't open <span class="mono slug">{{ slug }}</span>.</h1>
        <h1 v-else>Open workspace <span class="mono slug">{{ slug }}</span></h1>
        <p class="muted lead">
          <template v-if="ws.state === 'invalid'">
            The key stored in this browser was rejected by the API (it may have been rotated, or it belongs to another workspace). Paste the
            current key to continue.
          </template>
          <template v-else>Every workspace is scoped by its API key. Paste the key you received when the workspace was created.</template>
        </p>
        <form class="form" @submit.prevent="submit">
          <Input v-model="pasted" mono placeholder="cmx_…" aria-label="Workspace API key" autocomplete="off" :error="keyError" name="key" />
          <Button type="submit" variant="primary" :loading="busy">Open</Button>
        </form>
        <p class="foot muted">Don't have a key? <router-link class="lnk" to="/">Create a new workspace</router-link> — it takes one step.</p>
      </template>
    </div>
  </div>
</template>

<style scoped>
.gate { min-height: 100dvh; display: grid; place-items: center; padding: 24px; }
.box { width: 100%; max-width: 520px; display: flex; flex-direction: column; gap: 12px; }
.eyebrow { margin-top: 24px; }
.eyebrow.err { color: var(--error); }
h1 { font-size: var(--fs-24); line-height: 1.25; }
.slug { font-size: 0.8em; color: var(--text); background: var(--surface-2); padding: 2px 6px; border-radius: 4px; border: 1px solid var(--border); }
.lead { font-size: var(--fs-14); line-height: 1.55; max-width: 52ch; }
.lead code { color: var(--text); }
.detail { font-size: var(--fs-12); color: var(--muted); }
.form { display: grid; grid-template-columns: 1fr auto; gap: 8px; align-items: start; margin-top: 8px; }
.actions { display: flex; gap: 8px; margin-top: 8px; }
.foot { font-size: var(--fs-13); margin-top: 6px; }
.lnk { color: var(--accent); }
.lnk:hover { text-decoration: underline; }
@media (max-width: 480px) { .form { grid-template-columns: 1fr; } }
</style>
