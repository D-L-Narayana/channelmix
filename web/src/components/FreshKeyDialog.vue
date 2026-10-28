<script setup lang="ts">
/** Shows the API key exactly once after creation/rotation. */
import { computed, ref } from 'vue'
import { useWorkspaceStore } from '../stores/workspace'
import Dialog from './ui/Dialog.vue'
import Button from './ui/Button.vue'
import CopyButton from './CopyButton.vue'

const ws = useWorkspaceStore()
const ack = ref(false)
const magic = computed(() => (ws.slug && ws.freshKey ? `${location.origin}/w/${ws.slug}?key=${ws.freshKey}` : ''))
function close() {
  ack.value = false
  ws.dismissFreshKey()
}
</script>

<template>
  <Dialog :open="!!ws.freshKey" title="Your workspace key" description="Shown once. It is stored hashed on the server and cannot be recovered — copy it now." size="md" :closable="false">
    <div class="stack gap-4">
      <div class="field">
        <div class="lbl">API key</div>
        <div class="keybox">
          <code class="mono key" data-testid="fresh-key">{{ ws.freshKey }}</code>
          <CopyButton :text="ws.freshKey ?? ''" label="Copy key" />
        </div>
      </div>
      <div class="field">
        <div class="lbl">Magic link <span class="muted">(opens this workspace in any browser)</span></div>
        <div class="keybox">
          <code class="mono key small">{{ magic }}</code>
          <CopyButton :text="magic" label="Copy link" />
        </div>
      </div>
      <p class="muted note">This browser remembers the key in <span class="mono">localStorage</span>. Anyone with the key or link can read and write this workspace.</p>
      <label class="ack"><input v-model="ack" type="checkbox" /> I've saved the key somewhere safe</label>
    </div>
    <template #footer>
      <Button variant="primary" :disabled="!ack" data-autofocus @click="close">Continue to workspace</Button>
    </template>
  </Dialog>
</template>

<style scoped>
.lbl { font-size: var(--fs-13); font-weight: 500; margin-bottom: 6px; }
.keybox { display: flex; align-items: center; gap: 8px; padding: 8px 8px 8px 12px; background: var(--bg); border: 1px solid var(--border); border-radius: var(--r-md); }
.key { flex: 1; min-width: 0; overflow-wrap: anywhere; font-size: var(--fs-13); color: var(--text-strong); }
.key.small { font-size: var(--fs-12); color: var(--text); }
.note { font-size: var(--fs-13); line-height: 1.5; }
.ack { display: flex; align-items: center; gap: 8px; font-size: var(--fs-14); cursor: pointer; }
.ack input { width: 16px; height: 16px; accent-color: var(--accent); }
</style>
