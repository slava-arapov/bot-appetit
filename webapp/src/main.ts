import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import { initTelegram } from './telegram'

async function bootstrap() {
  if (import.meta.env.DEV) {
    // в prod-сборку mock не попадает: import.meta.env.DEV заменяется на false при сборке
    const { installMock } = await import('./telegram/mock')
    await installMock()
  }
  initTelegram()
  createApp(App).use(router).mount('#app')
}

bootstrap()
