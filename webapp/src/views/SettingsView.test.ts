import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import SettingsView from './SettingsView.vue'
import { createMockWebApp } from '../telegram/mock'

const api = vi.hoisted(() => ({ getSettings: vi.fn(), patchSettings: vi.fn() }))
vi.mock('../api/client', () => api)

beforeEach(() => {
  vi.useFakeTimers()
  api.getSettings.mockReset().mockResolvedValue({ servings: 2, cooking_time: '30' })
  api.patchSettings.mockReset().mockResolvedValue({ servings: 3, cooking_time: '30' })
  window.Telegram = { WebApp: createMockWebApp('x') }
})

afterEach(() => {
  vi.useRealTimers()
  delete window.Telegram
})

describe('SettingsView', () => {
  it('пока идёт загрузка, показывает скелетон, а не контролы', () => {
    api.getSettings.mockReturnValue(new Promise(() => undefined))
    const w = mount(SettingsView)
    expect(w.find('.van-skeleton').exists()).toBe(true)
    expect(w.find('[role="radiogroup"]').exists()).toBe(false)
  })

  it('после загрузки показывает текущие значения', async () => {
    const w = mount(SettingsView)
    await flushPromises()
    expect(w.get('output').text()).toBe('2')
    expect(w.get('[role="radio"][aria-checked="true"]').text()).toBe('30 мин')
  })

  it('тап по «+» сохраняет новое значение', async () => {
    const w = mount(SettingsView)
    await flushPromises()

    await w.get('[aria-label="Больше порций"]').trigger('click')
    expect(w.get('output').text()).toBe('3')

    await vi.advanceTimersByTimeAsync(300)
    expect(api.patchSettings).toHaveBeenCalledWith({ servings: 3 })
  })

  it('при ошибке загрузки показывает сообщение и кнопку «Повторить»', async () => {
    api.getSettings.mockRejectedValueOnce(new Error('нет сети'))
    const w = mount(SettingsView)
    await flushPromises()

    expect(w.text()).toContain('Не удалось загрузить настройки')
    await w.get('[data-test="reload"]').trigger('click')
    await flushPromises()

    expect(w.get('output').text()).toBe('2')
  })
})
