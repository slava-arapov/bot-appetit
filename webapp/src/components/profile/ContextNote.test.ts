import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ContextNote from './ContextNote.vue'

describe('ContextNote', () => {
  it('показывает текст, дату обновления и «Очистить»', () => {
    const w = mount(ContextNote, {
      props: { context: { notes: 'ужин на двоих', updated: '2026-10-18' } },
    })
    expect(w.get('[data-test="notes"]').text()).toBe('ужин на двоих')
    expect(w.get('[data-test="updated"]').text()).toBe('обновлено 18 окт')
    expect(w.find('[data-test="clear"]').exists()).toBe(true)
  })

  it('без даты не показывает подпись «обновлено»', () => {
    const w = mount(ContextNote, { props: { context: { notes: 'ужин', updated: '' } } })
    expect(w.find('[data-test="updated"]').exists()).toBe(false)
  })

  it('без заметки показывает «Пока ничего» и не даёт очистить', () => {
    const w = mount(ContextNote, { props: { context: { notes: '', updated: '' } } })
    expect(w.text()).toContain('Пока ничего')
    expect(w.find('[data-test="clear"]').exists()).toBe(false)
  })

  it('по нажатию «Очистить» отдаёт событие clear', async () => {
    const w = mount(ContextNote, { props: { context: { notes: 'ужин', updated: '' } } })
    await w.get('[data-test="clear"]').trigger('click')
    expect(w.emitted('clear')).toHaveLength(1)
  })
})
