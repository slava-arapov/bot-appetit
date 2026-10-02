import type { ThemeParams, WebApp } from './types'

const THEME_VARS: Record<keyof ThemeParams, string> = {
  bg_color: '--tg-bg',
  text_color: '--tg-text',
  hint_color: '--tg-hint',
  button_color: '--tg-button',
  button_text_color: '--tg-button-text',
  destructive_text_color: '--tg-destructive',
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

/** Схема клиента Telegram (light/dark) для стилей, которым не хватает themeParams, например цветов статусов. */
export function applyScheme(app: WebApp, root: HTMLElement = document.documentElement) {
  root.dataset.scheme = app.colorScheme
}

/** Сообщает Telegram, что приложение готово, и держит тему и высоту в синхроне с клиентом. */
export function initTelegram() {
  const app = getWebApp()
  const sync = () => {
    applyTheme(app.themeParams)
    applyScheme(app)
    applyViewport(app)
  }
  sync()
  app.onEvent('themeChanged', sync)
  app.onEvent('viewportChanged', sync)
  app.ready()
  app.expand()
}
