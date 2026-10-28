import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ToastTone = 'neutral' | 'success' | 'error' | 'warning'
export interface Toast {
  id: number
  title: string
  body?: string
  tone: ToastTone
  timeout: number
  action?: { label: string; onClick: () => void }
}

let seq = 0

export const useToastStore = defineStore('toast', () => {
  const items = ref<Toast[]>([])

  function push(t: Omit<Toast, 'id' | 'timeout' | 'tone'> & { tone?: ToastTone; timeout?: number }) {
    const toast: Toast = { id: ++seq, tone: 'neutral', timeout: 5000, ...t }
    items.value = [...items.value.slice(-3), toast]
    if (toast.timeout > 0) setTimeout(() => dismiss(toast.id), toast.timeout)
    return toast.id
  }
  function dismiss(id: number) {
    items.value = items.value.filter((t) => t.id !== id)
  }
  const success = (title: string, body?: string) => push({ title, body, tone: 'success' })
  const error = (title: string, body?: string) => push({ title, body, tone: 'error', timeout: 8000 })
  const info = (title: string, body?: string) => push({ title, body })

  return { items, push, dismiss, success, error, info }
})
