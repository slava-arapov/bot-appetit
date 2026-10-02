import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import type { PantryItem } from '../api/client'
import PantryView from './PantryView.vue'
import { useSnackbar } from '../composables/useSnackbar'
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

const items = [
  item({ id: 1, name: 'Молоко', status: 'have' }),
  item({ id: 2, name: 'Сыр', status: 'low', quantity: '200 г' }),
  item({ id: 3, name: 'Хлеб', status: 'to_buy' }),
]

beforeEach(() => {
  api.getPantry.mockReset().mockResolvedValue({ items, expiry_warning_days: 3 })
  api.patchPantryItem
    .mockReset()
    .mockImplementation(async (id: number, changes: Partial<PantryItem>) => ({
      ...items.find((i) => i.id === id)!,
      ...changes,
    }))
  api.createPantryItem
    .mockReset()
    .mockImplementation(async (body: Partial<PantryItem>) => item({ id: 99, ...body }))
  api.deletePantryItem.mockReset().mockResolvedValue(undefined)
  useSnackbar().dismiss()
  window.Telegram = { WebApp: createMockWebApp('x') }
})

afterEach(() => {
  delete window.Telegram
})

async function mountView() {
  const w = mount(PantryView)
  await flushPromises()
  return w
}

describe('PantryView', () => {
  it('пока идёт загрузка, показывает скелетон', () => {
    api.getPantry.mockReturnValue(new Promise(() => undefined))
    const w = mount(PantryView)
    expect(w.find('.van-skeleton').exists()).toBe(true)
  })

  it('показывает секции в порядке «Мало», «Нужно купить», «Есть»', async () => {
    const w = await mountView()
    const headings = w.findAll('h2').map((h) => h.text())
    expect(headings).toEqual([
      expect.stringContaining('Мало'),
      expect.stringContaining('Нужно купить'),
      expect.stringContaining('Есть'),
    ])
    expect(w.text()).toContain('Сыр')
  })

  it('тап по чипу меняет статус и сохраняет его', async () => {
    const w = await mountView()
    const cheeseChip = w.findAll('[data-test="status-chip"]')[0] // «Сыр», low
    await cheeseChip.trigger('click')
    await flushPromises()

    expect(api.patchPantryItem).toHaveBeenCalledWith(2, { status: 'to_buy' })
  })

  it('пустой список показывает приглашение добавить первый продукт', async () => {
    api.getPantry.mockResolvedValue({ items: [], expiry_warning_days: 3 })
    const w = await mountView()

    expect(w.text()).toContain('Добавь первый продукт')
    await w.get('[data-test="empty-add"]').trigger('click')
    await flushPromises()
    expect(w.text()).toContain('Новый продукт')
  })

  it('добавление через «+»: форма, сохранение, закрытие', async () => {
    const w = await mountView()

    await w.get('[aria-label="Добавить продукт"]').trigger('click')
    await flushPromises()
    await w.get('[data-test="name"]').setValue('Масло')
    await w.get('[data-test="submit"]').trigger('click')
    await flushPromises()

    expect(api.createPantryItem).toHaveBeenCalledWith({
      name: 'Масло',
      status: 'have',
      quantity: null,
      expiry_date: null,
    })
    expect(w.text()).toContain('Масло')
  })

  it('правка отправляет только изменённые поля', async () => {
    const w = await mountView()

    await w.findAll('[data-test="open"]')[0].trigger('click') // «Сыр»
    await flushPromises()
    await w.get('[data-test="quantity"]').setValue('100 г')
    await w.get('[data-test="submit"]').trigger('click')
    await flushPromises()

    expect(api.patchPantryItem).toHaveBeenCalledWith(2, { quantity: '100 г' })
  })

  it('удаление из формы правки убирает позицию и предлагает отменить', async () => {
    const w = await mountView()

    await w.findAll('[data-test="open"]')[0].trigger('click')
    await flushPromises()
    await w.get('[data-test="delete"]').trigger('click')
    await flushPromises()

    expect(api.deletePantryItem).toHaveBeenCalledWith(2)
    expect(useSnackbar().current.value?.message).toBe('Удалено · Сыр')
  })

  it('при ошибке загрузки показывает сообщение и «Повторить»', async () => {
    api.getPantry.mockRejectedValueOnce(new Error('нет сети'))
    const w = await mountView()

    expect(w.text()).toContain('Не удалось загрузить запасы')
    await w.get('[data-test="reload"]').trigger('click')
    await flushPromises()

    expect(w.text()).toContain('Сыр')
  })
})
