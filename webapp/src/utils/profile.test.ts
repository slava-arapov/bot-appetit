import { describe, expect, it } from 'vitest'
import { formatContextDate, normalizeTag, sameValue } from './profile'

describe('normalizeTag', () => {
  it('обрезает пробелы и приводит к нижнему регистру', () => {
    expect(normalizeTag('  Сыр ')).toBe('сыр')
    expect(normalizeTag('Кухонный Комбайн')).toBe('кухонный комбайн')
  })
})

describe('formatContextDate', () => {
  it('форматирует дату как «18 окт» без точки', () => {
    expect(formatContextDate('2026-10-18')).toBe('18 окт')
    expect(formatContextDate('2026-05-01')).toBe('1 мая')
  })

  it('пустую или битую строку не форматирует', () => {
    expect(formatContextDate('')).toBeNull()
    expect(formatContextDate('вчера')).toBeNull()
  })
})

describe('sameValue', () => {
  it('сравнивает без учёта регистра и пробелов по краям', () => {
    expect(sameValue('Духовка', ' духовка ')).toBe(true)
    expect(sameValue('духовка', 'плита')).toBe(false)
  })
})
