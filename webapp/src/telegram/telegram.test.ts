import { afterEach, describe, expect, it, vi } from 'vitest'
import { applyTheme, applyViewport, initTelegram } from './index'
import { createMockWebApp, installMock } from './mock'

afterEach(() => {
  delete window.Telegram
  document.documentElement.removeAttribute('style')
})

describe('applyTheme', () => {
  it('переносит themeParams в CSS-переменные и убирает отсутствующие', () => {
    applyTheme({ bg_color: '#111111', text_color: '#eeeeee' })
    const s = document.documentElement.style
    expect(s.getPropertyValue('--tg-bg')).toBe('#111111')
    expect(s.getPropertyValue('--tg-text')).toBe('#eeeeee')

    applyTheme({ bg_color: '#222222' })
    expect(s.getPropertyValue('--tg-bg')).toBe('#222222')
    expect(s.getPropertyValue('--tg-text')).toBe('')
  })
})

describe('applyViewport', () => {
  it('использует viewportStableHeight', () => {
    const app = createMockWebApp('x')
    app.viewportStableHeight = 640
    applyViewport(app)
    expect(document.documentElement.style.getPropertyValue('--tg-viewport-height')).toBe('640px')
  })
})

describe('initTelegram', () => {
  it('пересчитывает тему по themeChanged', () => {
    window.Telegram = { WebApp: createMockWebApp('x', 'light') }
    initTelegram()
    expect(document.documentElement.style.getPropertyValue('--tg-bg')).toBe('#ffffff')

    const controls = (window as unknown as { __tgMock: { setTheme(t: 'dark'): void } }).__tgMock
    controls.setTheme('dark')
    expect(document.documentElement.style.getPropertyValue('--tg-bg')).toBe('#212121')
  })
})

describe('installMock', () => {
  it('подменяет WebApp, когда initData пуст (вне Telegram)', async () => {
    window.Telegram = { WebApp: { initData: '' } as never }
    await installMock(async () => 'signed')
    expect(window.Telegram?.WebApp.initData).toBe('signed')
  })

  it('не трогает реальный Telegram с непустым initData', async () => {
    const real = { initData: 'real' } as never
    window.Telegram = { WebApp: real }
    const getInitData = vi.fn(async () => 'signed')
    await installMock(getInitData)
    expect(window.Telegram?.WebApp).toBe(real)
    expect(getInitData).not.toHaveBeenCalled()
  })
})
