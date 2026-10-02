import { createApp } from 'vue'
import './styles/base.css'
import App from './App.vue'
import { router } from './router'
import { initTelegram } from './telegram'
import { bindBackButton } from './telegram/backButton'

async function bootstrap() {
  if (import.meta.env.DEV) {
    // в prod-сборку mock не попадает: import.meta.env.DEV заменяется на false при сборке
    const { installMock } = await import('./telegram/mock')
    await installMock()
  }
  initTelegram()
  // до app.use(router): иначе первая навигация пройдёт раньше подписки на afterEach
  bindBackButton(router)
  createApp(App).use(router).mount('#app')
}

bootstrap()
