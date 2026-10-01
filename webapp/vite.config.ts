import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { devInitData } from './dev/init-data-plugin'

export default defineConfig({
  plugins: [vue(), devInitData()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8080',
    },
  },
  test: {
    environment: 'jsdom',
  },
})
