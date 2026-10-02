import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import type { Tag } from '../../api/client'
import EquipmentChecklist from './EquipmentChecklist.vue'

const OPTIONS = ['духовка', 'плита', 'блендер', 'мультиварка']

const mountList = (tags: Tag[] = [], options: string[] = OPTIONS) =>
  mount(EquipmentChecklist, { props: { options, tags } })

const labels = (w: ReturnType<typeof mountList>) =>
  w.findAll('[data-test="item"]').map((i) => i.text())

const checkbox = (w: ReturnType<typeof mountList>, name: string) =>
  w
    .findAll('[data-test="item"]')
    .find((i) => i.text() === name)!
    .get('input')

describe('EquipmentChecklist', () => {
  it('показывает частый список техники, всё не отмечено', () => {
    const w = mountList()
    expect(labels(w)).toEqual(OPTIONS)
    expect(w.findAll('input:checked')).toHaveLength(0)
  })

  it('отмечает то, что уже сохранено, без учёта регистра', () => {
    // в БД теги уже в нижнем регистре, но старый «Духовка» не должен дать двойной пункт
    const w = mountList([{ id: 1, value: 'Духовка' }])
    expect((checkbox(w, 'духовка').element as HTMLInputElement).checked).toBe(true)
    expect(labels(w)).toHaveLength(OPTIONS.length) // дубля нет
  })

  it('кастомные пункты из тегов идут в тот же список, отмеченными', () => {
    const w = mountList([{ id: 1, value: 'казан' }])
    expect(labels(w)).toEqual([...OPTIONS, 'казан'])
    expect((checkbox(w, 'казан').element as HTMLInputElement).checked).toBe(true)
  })

  it('тап по пункту просит переключить его', async () => {
    const w = mountList()
    await checkbox(w, 'блендер').trigger('change')
    expect(w.emitted('toggle')).toEqual([['блендер']])
  })

  it('«+ своё» добавляет пункт, очищает поле и не закрывает форму', async () => {
    const w = mountList()
    const input = w.get('[data-test="custom-input"]')

    await input.setValue('  Казан ')
    await w.get('[data-test="custom-add"]').trigger('click')

    expect(w.emitted('add')).toEqual([['казан']])
    expect((input.element as HTMLInputElement).value).toBe('')
    expect(w.find('[data-test="custom-input"]').exists()).toBe(true)
  })

  it('поле «своё» приводит буквы к нижнему регистру и не даёт заглавную на мобильной клавиатуре', async () => {
    const w = mountList()
    const input = w.get('[data-test="custom-input"]')

    await input.setValue('Казан Чугунный')

    expect((input.element as HTMLInputElement).value).toBe('казан чугунный')
    expect(input.attributes('autocapitalize')).toBe('none')
  })

  it('выключенный кастомный пункт остаётся в списке до перезагрузки экрана', async () => {
    const w = mountList([{ id: 1, value: 'казан' }])
    await w.setProps({ tags: [] })

    expect(labels(w)).toContain('казан')
    expect((checkbox(w, 'казан').element as HTMLInputElement).checked).toBe(false)
  })

  it('список пунктов берётся из пропса, а не зашит в компоненте', () => {
    const w = mountList([], ['казан', 'вок'])
    expect(labels(w)).toEqual(['казан', 'вок'])
  })

  it('пока список не пришёл, не рисует пунктов', () => {
    expect(labels(mountList([], []))).toEqual([])
  })
})
