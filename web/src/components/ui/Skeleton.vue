<script setup lang="ts">
withDefaults(defineProps<{ width?: string; height?: string; radius?: string; inline?: boolean }>(), {
  width: '100%',
  height: '14px',
  radius: '6px',
})
</script>

<template>
  <span class="sk" :class="{ inline }" :style="{ width, height, borderRadius: radius }" aria-hidden="true" />
</template>

<style scoped>
.sk {
  display: block;
  background: linear-gradient(90deg, var(--surface-2) 0%, var(--surface-3) 50%, var(--surface-2) 100%);
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
}
.inline { display: inline-block; vertical-align: middle; }
@keyframes shimmer { 0% { background-position: 100% 0; } 100% { background-position: -100% 0; } }
@media (prefers-reduced-motion: reduce) { .sk { animation: none; background: var(--surface-3); } }
</style>
