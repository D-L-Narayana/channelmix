/// <reference types="vitest" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.test.ts'],
    setupFiles: ['src/__tests__/setup.ts'],
    alias: { 'vue-echarts': new URL('./src/__tests__/vchart-stub.ts', import.meta.url).pathname },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: { echarts: ['echarts', 'vue-echarts'] },
      },
    },
  },
})
