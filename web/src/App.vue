<script setup lang="ts">
import ToastHost from './components/ui/Toast.vue'
</script>

<template>
  <a class="skip" href="#main">Skip to content</a>
  <router-view v-slot="{ Component }">
    <component :is="Component" />
  </router-view>
  <ToastHost />
</template>

<style scoped>
.skip {
  position: absolute; left: 12px; top: -48px; z-index: 100;
  padding: 8px 12px; background: var(--accent); color: var(--accent-ink); border-radius: var(--r-sm); font-weight: 500;
}
.skip:focus { top: 12px; }
</style>
