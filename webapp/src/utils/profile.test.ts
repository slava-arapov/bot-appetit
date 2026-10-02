import { describe, expect, it } from 'vitest'
import { DEFAULT_EQUIPMENT, normalizeTag, sameValue } from './profile'

describe('normalizeTag', () => {
  it('обрезает пробелы и приводит к нижнему регистру', () => {
    expect(normalizeTag('  Сыр ')).toBe('сыр')
    expect(normalizeTag('Кухонный Комбайн')).toBe('кухонный комбайн')
  })
})

describe('DEFAULT_EQUIPMENT', () => {
  it('весь список в нижнем регистре, как и теги в БД', () => {
    expect(DEFAULT_EQUIPMENT.filter((name) => name !== normalizeTag(name))).toEqual([])
  })

  it('без дублей', () => {
    expect(new Set(DEFAULT_EQUIPMENT).size).toBe(DEFAULT_EQUIPMENT.length)
  })
})

describe('sameValue', () => {
  it('сравнивает без учёта регистра и пробелов по краям', () => {
    expect(sameValue('Духовка', ' духовка ')).toBe(true)
    expect(sameValue('духовка', 'плита')).toBe(false)
  })
})
