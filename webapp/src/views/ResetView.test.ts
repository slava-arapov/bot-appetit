import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ResetView from './ResetView.vue'
import { createMockWebApp } from '../telegram/mock'
import { useSnackbar } from '../composables/useSnackbar'

const api = vi.hoisted(() => ({ resetMemory: vi.fn() }))
vi.mock('../api/client', () => api)

beforeEach(() => {
  api.resetMemory.mockReset().mockResolvedValue(undefined)
  window.Telegram = { WebApp: createMockWebApp('x') }
})

afterEach(() => {
  useSnackbar().dismiss()
  delete window.Telegram
})

const mountView = () => mount(ResetView, { attachTo: document.body })
const inBody = (test: string) => document.body.querySelector(`[data-test="${test}"]`) as HTMLElement | null

describe('ResetView', () => {
  it('сброс переписки выполняется сразу, без подтверждения', async () => {
    const w = mountView()
    await w.get('[data-test="reset-chat"]').trigger('click')
    await flushPromises()

    expect(api.resetMemory).toHaveBeenCalledWith('chat')
    expect(w.get('[data-test="done"]').text()).toContain('Переписка забыта')
    w.unmount()
  })

  it.each(['onboarding', 'all'] as const)('«%s» сначала спрашивает подтверждение', async (action) => {
    const w = mountView()
    await w.get(`[data-test="reset-${action}"]`).trigger('click')
    await flushPromises()

    expect(api.resetMemory).not.toHaveBeenCalled()
    expect(inBody('confirm-text')).not.toBeNull()

    inBody('confirm')!.click()
    await flushPromises()

    expect(api.resetMemory).toHaveBeenCalledWith(action)
    expect(w.get('[data-test="done"]').text()).toContain('/start')
    w.unmount()
  })

  it('отмена подтверждения ничего не сбрасывает', async () => {
    const w = mountView()
    await w.get('[data-test="reset-all"]').trigger('click')
    await flushPromises()
    inBody('cancel')!.click()
    await flushPromises()

    expect(api.resetMemory).not.toHaveBeenCalled()
    expect(w.find('[data-test="done"]').exists()).toBe(false)
    w.unmount()
  })

  it('ошибка сброса показывает снекбар и не пишет об успехе', async () => {
    api.resetMemory.mockRejectedValue(new Error('boom'))
    const w = mountView()
    await w.get('[data-test="reset-chat"]').trigger('click')
    await flushPromises()

    expect(useSnackbar().current.value?.message).toBe('Не удалось сбросить')
    expect(w.find('[data-test="done"]').exists()).toBe(false)
    w.unmount()
  })
})
