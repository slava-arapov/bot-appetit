import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ApiError, type PantryItem } from '../api/client'
import { usePantry } from './usePantry'
import { useSnackbar } from './useSnackbar'
import { createMockWebApp } from '../telegram/mock'

const api = vi.hoisted(() => ({
  getPantry: vi.fn(),
  createPantryItem: vi.fn(),
  patchPantryItem: vi.fn(),
  deletePantryItem: vi.fn(),
}))
vi.mock('../api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api/client')>()),
  ...api,
}))

const item = (over: Partial<PantryItem>): PantryItem => ({
  id: 1,
  name: 'Молоко',
  status: 'have',
  quantity: null,
  expiry_date: null,
  added_date: '2026-10-01',
  ...over,
})

const initial = [
  item({ id: 1, name: 'Молоко', status: 'have' }),
  item({ id: 2, name: 'Сыр', status: 'low', quantity: '200 г' }),
  item({ id: 3, name: 'Хлеб', status: 'to_buy' }),
  item({ id: 4, name: 'Яйца', status: 'have' }),
]

beforeEach(() => {
  api.getPantry.mockReset().mockResolvedValue({ items: initial, expiry_warning_days: 3 })
  api.patchPantryItem
    .mockReset()
    .mockImplementation(async (id: number, patch: Partial<PantryItem>) => ({
      ...initial.find((i) => i.id === id)!,
      ...patch,
    }))
  api.createPantryItem
    .mockReset()
    .mockImplementation(async (body: Partial<PantryItem>) =>
      item({ id: 99, quantity: null, expiry_date: null, ...body }),
    )
  api.deletePantryItem.mockReset().mockResolvedValue(undefined)
  useSnackbar().dismiss()
  window.Telegram = { WebApp: createMockWebApp('x') }
})

afterEach(() => {
  vi.useRealTimers()
  delete window.Telegram
})

async function ready() {
  const store = usePantry()
  await flushPromises()
  return store
}

const status = (store: Awaited<ReturnType<typeof ready>>, id: number) =>
  store.items.value.find((i) => i.id === id)?.status

describe('usePantry: загрузка и секции', () => {
  it('загружает позиции и окно срока годности', async () => {
    const { loading, items, expiryWarningDays } = usePantry()
    expect(loading.value).toBe(true)
    await flushPromises()
    expect(loading.value).toBe(false)
    expect(items.value).toHaveLength(4)
    expect(expiryWarningDays.value).toBe(3)
  })

  it('группирует в порядке «Мало» → «Нужно купить» → «Есть»', async () => {
    const { sections } = await ready()
    expect(sections.value.map((s) => [s.status, s.items.map((i) => i.name)])).toEqual([
      ['low', ['Сыр']],
      ['to_buy', ['Хлеб']],
      ['have', ['Молоко', 'Яйца']],
    ])
  })

  it('пустые секции не показывает', async () => {
    api.getPantry.mockResolvedValue({ items: [initial[0]], expiry_warning_days: 3 })
    const { sections } = await ready()
    expect(sections.value.map((s) => s.status)).toEqual(['have'])
  })

  it('при ошибке загрузки сохраняет сообщение', async () => {
    api.getPantry.mockRejectedValue(new Error('нет сети'))
    const { loading, loadError } = usePantry()
    await flushPromises()
    expect(loading.value).toBe(false)
    expect(loadError.value).toBe('нет сети')
  })
})

describe('usePantry: смена статуса', () => {
  it('cycleStatus переключает по кругу и сразу сохраняет', async () => {
    const store = await ready()

    store.cycleStatus(store.items.value[1]) // low → to_buy
    expect(status(store, 2)).toBe('to_buy')
    await flushPromises()

    expect(api.patchPantryItem).toHaveBeenCalledWith(2, { status: 'to_buy' })
  })

  it('при ошибке откатывает статус и предлагает повторить', async () => {
    const store = await ready()
    api.patchPantryItem.mockRejectedValueOnce(new Error('сервер недоступен'))

    store.cycleStatus(store.items.value[0]) // have → low
    await flushPromises()

    expect(status(store, 1)).toBe('have')
    expect(useSnackbar().current.value).toMatchObject({
      message: 'Не удалось сохранить',
      kind: 'error',
    })

    useSnackbar().act()
    await flushPromises()
    expect(status(store, 1)).toBe('low')
  })
})

describe('usePantry: добавление и правка', () => {
  it('add создаёт позицию и показывает её в списке', async () => {
    const store = await ready()

    const ok = await store.add({ name: 'Масло', status: 'to_buy' })

    expect(ok).toBe(true)
    expect(api.createPantryItem).toHaveBeenCalledWith({ name: 'Масло', status: 'to_buy' })
    expect(store.items.value.some((i) => i.name === 'Масло')).toBe(true)
  })

  it('add при ошибке возвращает false и показывает снекбар', async () => {
    const store = await ready()
    api.createPantryItem.mockRejectedValueOnce(new Error('нет сети'))

    expect(await store.add({ name: 'Масло' })).toBe(false)
    expect(store.items.value).toHaveLength(4)
    expect(useSnackbar().current.value?.message).toBe('Не удалось сохранить')
  })

  it('update применяет правку сразу и отправляет только изменённое', async () => {
    const store = await ready()

    const ok = await store.update(1, { quantity: '1 л' })

    expect(ok).toBe(true)
    expect(api.patchPantryItem).toHaveBeenCalledWith(1, { quantity: '1 л' })
    expect(store.items.value.find((i) => i.id === 1)?.quantity).toBe('1 л')
  })

  it('update при дубле названия (409) говорит об этом, а не «не удалось»', async () => {
    const store = await ready()
    api.patchPantryItem.mockRejectedValueOnce(new ApiError(409, 'дубль'))

    expect(await store.update(1, { name: 'Сыр' })).toBe(false)

    expect(useSnackbar().current.value?.message).toBe('Такая позиция уже есть')
    expect(store.items.value.find((i) => i.id === 1)?.name).toBe('Молоко')
  })
})

describe('usePantry: удаление и отмена', () => {
  it('remove убирает позицию сразу и предлагает отменить', async () => {
    const store = await ready()

    store.remove(store.items.value[0])
    expect(store.items.value.some((i) => i.id === 1)).toBe(false)
    await flushPromises()

    expect(api.deletePantryItem).toHaveBeenCalledWith(1)
    expect(useSnackbar().current.value).toMatchObject({
      message: 'Удалено · Молоко',
      kind: 'undo',
    })
  })

  it('«Отменить» создаёт позицию заново с теми же полями', async () => {
    const store = await ready()
    const cheese = store.items.value[1]

    store.remove(cheese)
    await flushPromises()
    useSnackbar().act()
    await flushPromises()

    expect(api.createPantryItem).toHaveBeenCalledWith({
      name: 'Сыр',
      status: 'low',
      quantity: '200 г',
      expiry_date: null,
    })
    expect(store.items.value.some((i) => i.name === 'Сыр')).toBe(true)
  })

  it('при ошибке удаления возвращает позицию на место', async () => {
    const store = await ready()
    api.deletePantryItem.mockRejectedValueOnce(new Error('нет сети'))

    store.remove(store.items.value[0])
    await flushPromises()

    expect(store.items.value.some((i) => i.id === 1)).toBe(true)
    expect(useSnackbar().current.value).toMatchObject({ kind: 'error' })
  })
})
