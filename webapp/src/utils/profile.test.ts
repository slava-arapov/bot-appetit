import { describe, expect, it } from 'vitest'
import { normalizeTag, sameValue } from './profile'

describe('normalizeTag', () => {
  it('обрезает пробелы и приводит к нижнему регистру', () => {
    expect(normalizeTag('  Сыр ')).toBe('сыр')
    expect(normalizeTag('Кухонный Комбайн')).toBe('кухонный комбайн')
  })
})

describe('sameValue', () => {
  it('сравнивает без учёта регистра и пробелов по краям', () => {
    expect(sameValue('Духовка', ' духовка ')).toBe(true)
    expect(sameValue('духовка', 'плита')).toBe(false)
  })
})
