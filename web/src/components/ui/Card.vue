<script setup lang="ts">
withDefaults(defineProps<{ title?: string; subtitle?: string; padded?: boolean; as?: string; flush?: boolean }>(), {
  padded: true,
  as: 'section',
})
</script>

<template>
  <component :is="as" class="card" :class="{ padded, flush }">
    <header v-if="title || $slots.title || $slots.actions" class="head">
      <div class="titles">
        <slot name="title"><h2 class="title">{{ title }}</h2></slot>
        <p v-if="subtitle" class="sub">{{ subtitle }}</p>
        <slot name="subtitle" />
      </div>
      <div v-if="$slots.actions" class="actions"><slot name="actions" /></div>
    </header>
    <div class="body"><slot /></div>
    <footer v-if="$slots.footer" class="foot"><slot name="footer" /></footer>
  </component>
</template>

<style scoped>
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-1);
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.padded .head { padding: 18px 20px 0; }
.padded .body { padding: 16px 20px 20px; }
.padded .foot { padding: 12px 20px; border-top: 1px solid var(--border); }
.flush .body { padding: 0; }
.flush .head { padding: 18px 20px 14px; }
.head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.titles { min-width: 0; }
.title { font-size: var(--fs-16); font-weight: 500; color: var(--text-strong); }
.sub { margin-top: 3px; font-size: var(--fs-13); color: var(--muted); }
.actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.body { flex: 1; min-width: 0; }
@media (max-width: 640px) {
  .padded .head { padding: 14px 14px 0; }
  .padded .body { padding: 12px 14px 14px; }
  .flush .head { padding: 14px 14px 10px; }
}
</style>
