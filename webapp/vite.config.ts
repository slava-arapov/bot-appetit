import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { VantResolver } from '@vant/auto-import-resolver'
import { devInitData } from './dev/init-data-plugin'

export default defineConfig({
  plugins: [
    vue(),
    // Vant подключается по компонентам (tree-shaking), без глобальной регистрации
    Components({ resolvers: [VantResolver()], dts: false }),
    devInitData(),
  ],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8080',
    },
  },
  test: {
    environment: 'jsdom',
    // Vant импортирует .css из node_modules: без inline Node не умеет их загружать
    server: { deps: { inline: ['vant'] } },
  },
})
