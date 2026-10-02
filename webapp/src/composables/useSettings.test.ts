import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { Settings } from '../api/client'
import { useSettings } from './useSettings'
import { useSnackbar } from './useSnackbar'
import { createMockWebApp } from '../telegram/mock'

const api = vi.hoisted(() => ({ getSettings: vi.fn(), patchSettings: vi.fn() }))
vi.mock('../api/client', () => api)

const initial: Settings = { servings: 2, cooking_time: '30' }

beforeEach(() => {
  vi.useFakeTimers()
  api.getSettings.mockReset().mockResolvedValue(initial)
  api.patchSettings.mockReset().mockImplementation(async (patch: Partial<Settings>) => ({
    ...initial,
    ...patch,
  }))
  useSnackbar().dismiss()
  window.Telegram = { WebApp: createMockWebApp('x') }
})

afterEach(() => {
  vi.useRealTimers()
  delete window.Telegram
})

async function ready() {
  const store = useSettings()
  await flushPromises()
  return store
}

describe('useSettings', () => {
  it('загружает настройки при создании', async () => {
    const { settings, loading } = useSettings()
    expect(loading.value).toBe(true)
    await flushPromises()
    expect(loading.value).toBe(false)
    expect(settings.value).toEqual(initial)
  })

  it('при ошибке загрузки сохраняет сообщение и не падает', async () => {
    api.getSettings.mockRejectedValue(new Error('нет сети'))
    const { settings, loading, loadError } = useSettings()
    await flushPromises()
    expect(loading.value).toBe(false)
    expect(settings.value).toBeNull()
    expect(loadError.value).toBe('нет сети')
  })

  it('setServings обновляет значение сразу, а запрос уходит после паузы', async () => {
    const { settings, setServings } = await ready()

    setServings(3)
    expect(settings.value?.servings).toBe(3)
    expect(api.patchSettings).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(300)
    expect(api.patchSettings).toHaveBeenCalledWith({ servings: 3 })
  })

  it('быстрые нажатия схлопываются в один запрос с последним значением', async () => {
    const { settings, setServings } = await ready()

    setServings(3)
    setServings(4)
    setServings(5)
    await vi.advanceTimersByTimeAsync(300)

    expect(api.patchSettings).toHaveBeenCalledOnce()
    expect(api.patchSettings).toHaveBeenCalledWith({ servings: 5 })
    expect(settings.value?.servings).toBe(5)
  })

  it('setServings не выходит за диапазон 1–8', async () => {
    const { settings, setServings } = await ready()

    setServings(9)
    expect(settings.value?.servings).toBe(8)
    setServings(0)
    expect(settings.value?.servings).toBe(1)
  })

  it('setServings из пустого значения начинает с 2', async () => {
    api.getSettings.mockResolvedValue({ servings: null, cooking_time: null })
    const { settings, stepServings } = await ready()

    stepServings(1)
    expect(settings.value?.servings).toBe(2)
  })

  it('setCookingTime отправляет запрос сразу', async () => {
    const { settings, setCookingTime } = await ready()

    setCookingTime('60')
    expect(settings.value?.cooking_time).toBe('60')
    await flushPromises()
    expect(api.patchSettings).toHaveBeenCalledWith({ cooking_time: '60' })
  })

  it('при ошибке откатывает значение и показывает снекбар с повтором', async () => {
    const { settings, setCookingTime } = await ready()
    api.patchSettings.mockRejectedValueOnce(new Error('сервер недоступен'))

    setCookingTime('60')
    await flushPromises()

    expect(settings.value?.cooking_time).toBe('30')
    expect(useSnackbar().current.value?.message).toBe('Не удалось сохранить')

    useSnackbar().act()
    await flushPromises()
    expect(api.patchSettings).toHaveBeenCalledTimes(2)
    expect(settings.value?.cooking_time).toBe('60')
  })

  it('успешное сохранение даёт haptic success', async () => {
    const app = createMockWebApp('x')
    const spy = vi.spyOn(app.HapticFeedback, 'notificationOccurred')
    window.Telegram = { WebApp: app }
    const { setCookingTime } = await ready()

    setCookingTime('15')
    await flushPromises()

    expect(spy).toHaveBeenCalledWith('success')
  })
})
