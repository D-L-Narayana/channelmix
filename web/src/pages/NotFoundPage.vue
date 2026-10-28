<script setup lang="ts">
import Wordmark from '../components/Wordmark.vue'
import Button from '../components/ui/Button.vue'
</script>

<template>
  <div class="nf">
    <div class="box">
      <Wordmark />
      <p class="eyebrow">404</p>
      <h1>There's nothing at this address.</h1>
      <p class="muted">Workspaces live at <span class="mono">/w/&lt;slug&gt;</span>. If you followed a magic link, make sure it wasn't cut off.</p>
      <div><Button variant="primary" to="/">Back to start</Button></div>
    </div>
  </div>
</template>

<style scoped>
.nf { min-height: 100dvh; display: grid; place-items: center; padding: 24px; }
.box { max-width: 480px; display: flex; flex-direction: column; gap: 12px; }
.eyebrow { margin-top: 20px; }
h1 { font-size: var(--fs-24); }
</style>
