// Минимальное подмножество Telegram.WebApp, которое реально использует приложение.
export interface ThemeParams {
  bg_color?: string
  text_color?: string
  hint_color?: string
  button_color?: string
  secondary_bg_color?: string
}

export type TelegramEvent = 'themeChanged' | 'viewportChanged'

export interface BackButton {
  isVisible: boolean
  show(): void
  hide(): void
  onClick(cb: () => void): void
  offClick(cb: () => void): void
}

export interface MainButton {
  isVisible: boolean
  isActive: boolean
  text: string
  show(): void
  hide(): void
  enable(): void
  disable(): void
  setText(text: string): void
  onClick(cb: () => void): void
  offClick(cb: () => void): void
}

export interface HapticFeedback {
  impactOccurred(style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft'): void
  notificationOccurred(type: 'error' | 'success' | 'warning'): void
  selectionChanged(): void
}

export interface WebApp {
  initData: string
  themeParams: ThemeParams
  colorScheme: 'light' | 'dark'
  viewportStableHeight: number
  BackButton: BackButton
  MainButton: MainButton
  HapticFeedback: HapticFeedback
  ready(): void
  expand(): void
  onEvent(event: TelegramEvent, cb: () => void): void
  offEvent(event: TelegramEvent, cb: () => void): void
}

declare global {
  interface Window {
    Telegram?: { WebApp: WebApp }
  }
}
