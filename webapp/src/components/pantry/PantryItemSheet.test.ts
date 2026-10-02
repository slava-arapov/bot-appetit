import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import type { PantryItem } from '../../api/client'
import PantryItemSheet from './PantryItemSheet.vue'

const cheese: PantryItem = {
  id: 1,
  name: 'Сыр',
  status: 'low',
  quantity: '200 г',
  expiry_date: '2026-10-04',
  added_date: '2026-10-01',
}

const mountSheet = (item: PantryItem | null = null) =>
  mount(PantryItemSheet, { props: { show: true, item } })

const submit = (w: ReturnType<typeof mountSheet>) => w.get('[data-test="submit"]')

describe('PantryItemSheet: добавление', () => {
  it('кнопка «Добавить» активна только при непустом названии', async () => {
    const w = mountSheet()
    expect(w.text()).toContain('Новый продукт')
    expect(submit(w).text()).toBe('Добавить')
    expect(submit(w).attributes('disabled')).toBeDefined()

    await w.get('[data-test="name"]').setValue('   ')
    expect(submit(w).attributes('disabled')).toBeDefined()

    await w.get('[data-test="name"]').setValue('Молоко')
    expect(submit(w).attributes('disabled')).toBeUndefined()
  })

  it('отправляет обрезанное название, статус «Есть» и пустые необязательные поля как null', async () => {
    const w = mountSheet()
    await w.get('[data-test="name"]').setValue('  Молоко ')
    await submit(w).trigger('click')

    expect(w.emitted('save')).toEqual([
      [{ name: 'Молоко', status: 'have', quantity: null, expiry_date: null }],
    ])
  })

  it('позволяет сразу записать продукт в «Нужно купить»', async () => {
    const w = mountSheet()
    await w.get('[data-test="name"]').setValue('Хлеб')
    const options = w.findAll('[role="radio"]')
    expect(options.map((o) => o.text())).toEqual(['Есть', 'Мало', 'Нужно купить'])

    await options[2].trigger('click')
    await submit(w).trigger('click')

    expect(w.emitted('save')?.[0][0]).toMatchObject({ name: 'Хлеб', status: 'to_buy' })
  })

  it('отправляет количество и срок годности', async () => {
    const w = mountSheet()
    await w.get('[data-test="name"]').setValue('Сыр')
    await w.get('[data-test="quantity"]').setValue('200 г')
    await w.get('[data-test="expiry"]').setValue('2026-10-04')
    await submit(w).trigger('click')

    expect(w.emitted('save')?.[0][0]).toEqual({
      name: 'Сыр',
      status: 'have',
      quantity: '200 г',
      expiry_date: '2026-10-04',
    })
  })

  it('в режиме добавления нет кнопки «Удалить»', () => {
    expect(mountSheet().find('[data-test="delete"]').exists()).toBe(false)
  })
})

describe('PantryItemSheet: правка', () => {
  it('подставляет значения позиции', () => {
    const w = mountSheet(cheese)
    expect(w.text()).toContain('Редактировать')
    expect(submit(w).text()).toBe('Сохранить')
    expect((w.get('[data-test="name"]').element as HTMLInputElement).value).toBe('Сыр')
    expect((w.get('[data-test="quantity"]').element as HTMLInputElement).value).toBe('200 г')
    expect((w.get('[data-test="expiry"]').element as HTMLInputElement).value).toBe('2026-10-04')
    expect(w.get('[role="radio"][aria-checked="true"]').text()).toBe('Мало')
  })

  it('есть видимая кнопка «Удалить» — альтернатива свайпу', async () => {
    const w = mountSheet(cheese)
    await w.get('[data-test="delete"]').trigger('click')
    expect(w.emitted('remove')).toHaveLength(1)
  })

  it('очищенное поле количества уходит как null', async () => {
    const w = mountSheet(cheese)
    await w.get('[data-test="quantity"]').setValue('')
    await submit(w).trigger('click')
    expect(w.emitted('save')?.[0][0]).toMatchObject({ quantity: null })
  })
})
