import type { ThemeParams, WebApp } from './types'

const THEME_VARS: Record<keyof ThemeParams, string> = {
  bg_color: '--tg-bg',
  text_color: '--tg-text',
  hint_color: '--tg-hint',
  button_color: '--tg-button',
  secondary_bg_color: '--tg-secondary-bg',
}

export function getWebApp(): WebApp {
  const app = window.Telegram?.WebApp
  if (!app) throw new Error('Telegram.WebApp недоступен')
  return app
}

export function applyTheme(params: ThemeParams, root: HTMLElement = document.documentElement) {
  for (const [key, cssVar] of Object.entries(THEME_VARS)) {
    const value = params[key as keyof ThemeParams]
    if (value) root.style.setProperty(cssVar, value)
    else root.style.removeProperty(cssVar)
  }
}

export function applyViewport(app: WebApp, root: HTMLElement = document.documentElement) {
  root.style.setProperty('--tg-viewport-height', `${app.viewportStableHeight}px`)
}

/** Сообщает Telegram, что приложение готово, и держит тему и высоту в синхроне с клиентом. */
export function initTelegram() {
  const app = getWebApp()
  const sync = () => {
    applyTheme(app.themeParams)
    applyViewport(app)
  }
  sync()
  app.onEvent('themeChanged', sync)
  app.onEvent('viewportChanged', sync)
  app.ready()
  app.expand()
}
