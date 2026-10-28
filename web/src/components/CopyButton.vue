<script setup lang="ts">
import { ref } from 'vue'
import Button from './ui/Button.vue'

const props = withDefaults(defineProps<{ text: string; label?: string; size?: 'sm' | 'md'; variant?: 'primary' | 'secondary' | 'ghost' }>(), {
  label: 'Copy',
  size: 'sm',
  variant: 'secondary',
})
const done = ref(false)
async function copy() {
  try {
    await navigator.clipboard.writeText(props.text)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = props.text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    ta.remove()
  }
  done.value = true
  setTimeout(() => (done.value = false), 1600)
}
</script>

<template>
  <Button :size="size" :variant="variant" :aria-label="`${label} to clipboard`" @click="copy">
    <span aria-live="polite">{{ done ? 'Copied' : label }}</span>
  </Button>
</template>
