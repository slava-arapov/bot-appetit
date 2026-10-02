import { afterEach, describe, expect, it, vi } from 'vitest'
import { haptic } from './haptic'
import { createMockWebApp } from './mock'

afterEach(() => {
  delete window.Telegram
})

describe('haptic', () => {
  it('success и error вызывают notificationOccurred', () => {
    const app = createMockWebApp('x')
    const spy = vi.spyOn(app.HapticFeedback, 'notificationOccurred')
    window.Telegram = { WebApp: app }

    haptic.success()
    haptic.error()

    expect(spy).toHaveBeenNthCalledWith(1, 'success')
    expect(spy).toHaveBeenNthCalledWith(2, 'error')
  })

  it('молча ничего не делает, если Telegram.WebApp недоступен', () => {
    expect(() => haptic.success()).not.toThrow()
  })

  it('молча ничего не делает, если у клиента нет HapticFeedback', () => {
    const app = createMockWebApp('x')
    Object.assign(app, { HapticFeedback: undefined })
    window.Telegram = { WebApp: app }

    expect(() => haptic.error()).not.toThrow()
  })
})
