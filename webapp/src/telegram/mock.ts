import type { TelegramEvent, ThemeParams, WebApp } from './types'

const THEMES: Record<'light' | 'dark', ThemeParams> = {
  light: {
    bg_color: '#ffffff',
    text_color: '#000000',
    hint_color: '#999999',
    button_color: '#2481cc',
    secondary_bg_color: '#f1f1f1',
  },
  dark: {
    bg_color: '#212121',
    text_color: '#ffffff',
    hint_color: '#aaaaaa',
    button_color: '#8774e1',
    secondary_bg_color: '#0f0f0f',
  },
}

type Listener = () => void

function createButtonState() {
  const listeners = new Set<Listener>()
  return {
    listeners,
    onClick: (cb: Listener) => void listeners.add(cb),
    offClick: (cb: Listener) => void listeners.delete(cb),
  }
}

export function createMockWebApp(initData: string, scheme: 'light' | 'dark' = 'light'): WebApp {
  const events = new Map<TelegramEvent, Set<Listener>>()
  const back = createButtonState()
  const main = createButtonState()

  const app: WebApp = {
    initData,
    themeParams: THEMES[scheme],
    colorScheme: scheme,
    viewportStableHeight: window.innerHeight,
    BackButton: {
      isVisible: false,
      show() {
        this.isVisible = true
      },
      hide() {
        this.isVisible = false
      },
      onClick: back.onClick,
      offClick: back.offClick,
    },
    MainButton: {
      isVisible: false,
      isActive: true,
      text: '',
      show() {
        this.isVisible = true
      },
      hide() {
        this.isVisible = false
      },
      enable() {
        this.isActive = true
      },
      disable() {
        this.isActive = false
      },
      setText(text) {
        this.text = text
      },
      onClick: main.onClick,
      offClick: main.offClick,
    },
    HapticFeedback: {
      impactOccurred: (style) => console.debug('[tg-mock] haptic impact', style),
      notificationOccurred: (type) => console.debug('[tg-mock] haptic notification', type),
      selectionChanged: () => console.debug('[tg-mock] haptic selection'),
    },
    ready: () => console.debug('[tg-mock] ready'),
    expand: () => undefined,
    onEvent: (event, cb) => {
      if (!events.has(event)) events.set(event, new Set())
      events.get(event)!.add(cb)
    },
    offEvent: (event, cb) => void events.get(event)?.delete(cb),
  }

  // Для ручной проверки в консоли: __tgMock.setTheme('dark'), __tgMock.pressBack()
  const controls = {
    setTheme(next: 'light' | 'dark') {
      app.colorScheme = next
      app.themeParams = THEMES[next]
      events.get('themeChanged')?.forEach((cb) => cb())
    },
    pressBack: () => back.listeners.forEach((cb) => cb()),
    pressMain: () => main.listeners.forEach((cb) => cb()),
  }
  Object.assign(window, { __tgMock: controls })
  return app
}

async function fetchDevInitData(): Promise<string> {
  const res = await fetch('/__dev/init-data')
  if (!res.ok) throw new Error(`/__dev/init-data: ${res.status}`)
  return res.text()
}

/** Подменяет Telegram.WebApp, если страница открыта не внутри Telegram (initData пуст). */
export async function installMock(getInitData: () => Promise<string> = fetchDevInitData) {
  if (window.Telegram?.WebApp?.initData) return
  const scheme = new URLSearchParams(location.search).get('theme') === 'dark' ? 'dark' : 'light'
  window.Telegram = { WebApp: createMockWebApp(await getInitData(), scheme) }
}
