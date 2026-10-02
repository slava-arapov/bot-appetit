import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import type { CookingTime } from '../../api/client'
import CookingTimeSegmented from './CookingTimeSegmented.vue'

const mountSegmented = (modelValue: CookingTime | null) =>
  mount(CookingTimeSegmented, { props: { modelValue } })

describe('CookingTimeSegmented', () => {
  it('рисует четыре варианта как radiogroup', () => {
    const w = mountSegmented(null)
    expect(w.find('[role="radiogroup"]').exists()).toBe(true)
    expect(w.findAll('[role="radio"]').map((r) => r.text())).toEqual([
      '15 мин',
      '30 мин',
      '60 мин',
      'Не важно',
    ])
  })

  it('отмечает выбранный вариант', () => {
    const radios = mountSegmented('60').findAll('[role="radio"]')
    expect(radios.map((r) => r.attributes('aria-checked'))).toEqual([
      'false',
      'false',
      'true',
      'false',
    ])
  })

  it('без значения ничего не выбрано, но в группу можно войти с клавиатуры', () => {
    const radios = mountSegmented(null).findAll('[role="radio"]')
    expect(radios.every((r) => r.attributes('aria-checked') === 'false')).toBe(true)
    expect(radios.map((r) => r.attributes('tabindex'))).toEqual(['0', '-1', '-1', '-1'])
  })

  it('клик выбирает вариант', async () => {
    const w = mountSegmented('30')
    await w.findAll('[role="radio"]')[3].trigger('click')
    expect(w.emitted('update:modelValue')).toEqual([['any']])
  })

  it('стрелки переключают вариант по кругу', async () => {
    const w = mountSegmented('any')
    await w.findAll('[role="radio"]')[3].trigger('keydown', { key: 'ArrowRight' })
    await w.findAll('[role="radio"]')[3].trigger('keydown', { key: 'ArrowLeft' })
    expect(w.emitted('update:modelValue')).toEqual([['15'], ['60']])
  })
})
