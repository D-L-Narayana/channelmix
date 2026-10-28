import { ref, watch } from 'vue'

/** Display currency is a frontend preference (the API stores plain amounts). Persisted per workspace slug. */
const KEY = 'channelmix.currency.'
export const displayCurrency = ref('USD')
let activeSlug: string | null = null

export function loadCurrency(slug: string) {
  activeSlug = slug
  try {
    displayCurrency.value = localStorage.getItem(KEY + slug) ?? 'USD'
  } catch {
    displayCurrency.value = 'USD'
  }
}
export function setCurrency(code: string) {
  const c = code.trim().toUpperCase()
  if (!/^[A-Z]{3}$/.test(c)) return
  displayCurrency.value = c
}
watch(displayCurrency, (c) => {
  if (!activeSlug) return
  try {
    localStorage.setItem(KEY + activeSlug, c)
  } catch {
    /* noop */
  }
})
export const CURRENCIES = ['USD', 'EUR', 'GBP', 'INR', 'AUD', 'CAD', 'SGD', 'AED', 'JPY', 'BRL']
