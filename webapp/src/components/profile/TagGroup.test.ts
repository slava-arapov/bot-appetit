import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import type { Tag } from '../../api/client'
import TagGroup from './TagGroup.vue'

const tags: Tag[] = [
  { id: 1, value: 'сыр' },
  { id: 2, value: 'хлеб' },
]

const mountGroup = (list: Tag[] = tags) =>
  mount(TagGroup, { props: { title: 'Любит', tags: list } })

describe('TagGroup', () => {
  it('показывает заголовок и теги', () => {
    const w = mountGroup()
    expect(w.get('h2').text()).toBe('Любит')
    expect(w.findAll('[data-test="tag"]').map((t) => t.text())).toEqual(['сыр', 'хлеб'])
  })

  it('пустая группа не скрывается и подсказывает, что делать', () => {
    const w = mountGroup([])
    expect(w.text()).toContain('Пока ничего не добавлено')
    expect(w.find('[data-test="input"]').exists()).toBe(true)
  })

  it('добавляет тег с обрезанными пробелами и очищает поле', async () => {
    const w = mountGroup()
    const input = w.get('[data-test="input"]')
    await input.setValue('  Рис ')
    await w.get('[data-test="add"]').trigger('click')

    expect(w.emitted('add')).toEqual([['рис']])
    expect((input.element as HTMLInputElement).value).toBe('')
  })

  it('приводит введённые буквы к нижнему регистру прямо в поле', async () => {
    const w = mountGroup()
    const input = w.get('[data-test="input"]')
    await input.setValue('Рис Басмати')
    expect((input.element as HTMLInputElement).value).toBe('рис басмати')
  })

  it('не сдвигает курсор при правке в середине слова', async () => {
    const w = mountGroup()
    const input = w.get('[data-test="input"]')
    const el = input.element as HTMLInputElement

    el.value = 'АБВ'
    el.setSelectionRange(1, 1)
    await input.trigger('input')

    expect(el.value).toBe('абв')
    expect(el.selectionStart).toBe(1)
    expect(el.selectionEnd).toBe(1)
  })

  it('просит мобильную клавиатуру не делать первую букву заглавной', () => {
    expect(mountGroup().get('[data-test="input"]').attributes('autocapitalize')).toBe('none')
  })

  it('не отправляет пустое значение', async () => {
    const w = mountGroup()
    await w.get('[data-test="input"]').setValue('   ')
    expect(w.get('[data-test="add"]').attributes('disabled')).toBeDefined()
    await w.get('[data-test="add"]').trigger('click')
    expect(w.emitted('add')).toBeUndefined()
  })

  it('крестик на теге просит удалить именно его', async () => {
    const w = mountGroup()
    const remove = w.get('[aria-label="Удалить хлеб"]')
    await remove.trigger('click')
    expect(w.emitted('remove')).toEqual([[tags[1]]])
  })
})
