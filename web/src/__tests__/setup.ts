// Global test setup (jsdom). Charts are stubbed via the vue-echarts alias in vite.config.ts.
import { createPinia, setActivePinia } from 'pinia'

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
})
