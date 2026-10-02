import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ServingsStepper from './ServingsStepper.vue'

const mountStepper = (value: number | null) =>
  mount(ServingsStepper, { props: { value, min: 1, max: 8 } })

const minus = (w: ReturnType<typeof mountStepper>) => w.get('[aria-label="Меньше порций"]')
const plus = (w: ReturnType<typeof mountStepper>) => w.get('[aria-label="Больше порций"]')

describe('ServingsStepper', () => {
  it('показывает значение', () => {
    expect(mountStepper(4).text()).toContain('4')
  })

  it('показывает прочерк, если значения нет', () => {
    expect(mountStepper(null).text()).toContain('—')
  })

  it('кнопки шлют step с направлением', async () => {
    const w = mountStepper(4)
    await plus(w).trigger('click')
    await minus(w).trigger('click')
    expect(w.emitted('step')).toEqual([[1], [-1]])
  })

  it('«−» заблокирована на минимуме и без значения', () => {
    expect(minus(mountStepper(1)).attributes('disabled')).toBeDefined()
    expect(minus(mountStepper(null)).attributes('disabled')).toBeDefined()
  })

  it('«+» заблокирована на максимуме', () => {
    expect(plus(mountStepper(8)).attributes('disabled')).toBeDefined()
    expect(plus(mountStepper(7)).attributes('disabled')).toBeUndefined()
  })

  it('значение объявляется скринридеру', () => {
    const w = mountStepper(3)
    expect(w.get('[role="group"]').attributes('aria-label')).toBe('Количество порций')
    expect(w.get('output').attributes('aria-live')).toBe('polite')
  })
})
