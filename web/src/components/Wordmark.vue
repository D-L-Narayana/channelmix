<script setup lang="ts">
withDefaults(defineProps<{ size?: 'sm' | 'md' | 'lg'; to?: string }>(), { size: 'md', to: '/' })
</script>

<template>
  <router-link :to="to" class="wm" :class="size" aria-label="ChannelMix home">
    <span class="mark" aria-hidden="true"><i /><i /><i /></span>
    <span class="name">Channel<b>Mix</b></span>
  </router-link>
</template>

<style scoped>
.wm { display: inline-flex; align-items: center; gap: 9px; color: var(--text-strong); font-weight: 500; letter-spacing: -0.01em; border-radius: 6px; }
.name b { font-weight: 600; color: var(--accent); }
.mark { display: inline-flex; align-items: flex-end; gap: 2px; height: 14px; }
.mark i { display: block; width: 4px; border-radius: 1px; background: var(--text-strong); }
.mark i:nth-child(1) { height: 7px; opacity: 0.55; }
.mark i:nth-child(2) { height: 14px; background: var(--accent); }
.mark i:nth-child(3) { height: 10px; opacity: 0.8; }
.sm { font-size: var(--fs-14); }
.md { font-size: var(--fs-16); }
.lg { font-size: var(--fs-20); }
.lg .mark { height: 18px; } .lg .mark i { width: 5px; } .lg .mark i:nth-child(1) { height: 9px; } .lg .mark i:nth-child(2) { height: 18px; } .lg .mark i:nth-child(3) { height: 13px; }
</style>
