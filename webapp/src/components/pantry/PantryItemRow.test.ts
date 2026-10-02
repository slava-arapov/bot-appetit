import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import type { PantryItem } from '../../api/client'
import PantryItemRow from './PantryItemRow.vue'

const base: PantryItem = {
  id: 1,
  name: 'Сыр',
  status: 'low',
  quantity: '200 г',
  expiry_date: '2026-10-04',
  added_date: '2026-10-01',
}

const mountRow = (over: Partial<PantryItem> = {}, expiring = false) =>
  mount(PantryItemRow, { props: { item: { ...base, ...over }, expiring } })

describe('PantryItemRow', () => {
  it('показывает название, количество и срок годности', () => {
    const text = mountRow().text()
    expect(text).toContain('Сыр')
    expect(text).toContain('200 г')
    expect(text).toContain('годен до 04.10')
  })

  it('если срок подходит, говорит об этом словами, а не только цветом', () => {
    const w = mountRow({}, true)
    expect(w.text()).toContain('истекает 04.10')
    expect(w.find('.row__meta--warn').exists()).toBe(true)
  })

  it('без количества и срока не рисует строку с подробностями', () => {
    const w = mountRow({ quantity: null, expiry_date: null })
    expect(w.find('.row__meta').exists()).toBe(false)
  })

  it('чип показывает статус и по тапу просит сменить его', async () => {
    const w = mountRow()
    const chip = w.get('[data-test="status-chip"]')
    expect(chip.text()).toBe('Мало')
    expect(chip.attributes('aria-label')).toContain('Мало')

    await chip.trigger('click')
    expect(w.emitted('cycle')).toHaveLength(1)
  })

  it('тап по названию открывает правку', async () => {
    const w = mountRow()
    await w.get('[data-test="open"]').trigger('click')
    expect(w.emitted('edit')).toHaveLength(1)
  })

  it('кнопка «Удалить» за свайпом просит удалить позицию', async () => {
    const w = mountRow()
    await w.get('[data-test="swipe-delete"]').trigger('click')
    expect(w.emitted('remove')).toHaveLength(1)
  })
})
