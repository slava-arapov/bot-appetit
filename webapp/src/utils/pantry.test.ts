import { describe, expect, it } from 'vitest'
import { formatExpiry, isExpiring, nextStatus, toISODate } from './pantry'

describe('nextStatus', () => {
  it('идёт по кругу have → low → to_buy → have', () => {
    expect(nextStatus('have')).toBe('low')
    expect(nextStatus('low')).toBe('to_buy')
    expect(nextStatus('to_buy')).toBe('have')
  })
})

describe('toISODate', () => {
  it('берёт локальную дату, а не UTC', () => {
    expect(toISODate(new Date(2026, 9, 1, 0, 30))).toBe('2026-10-01')
  })
})

describe('isExpiring', () => {
  const today = new Date(2026, 9, 1)

  it('истекает в пределах окна, включая границу', () => {
    expect(isExpiring('2026-10-04', 3, today)).toBe(true)
    expect(isExpiring('2026-10-05', 3, today)).toBe(false)
  })

  it('просроченное тоже подсвечивается', () => {
    expect(isExpiring('2026-09-01', 3, today)).toBe(true)
  })

  it('без срока годности не подсвечивается', () => {
    expect(isExpiring(null, 3, today)).toBe(false)
  })
})

describe('formatExpiry', () => {
  it('показывает день и месяц', () => {
    expect(formatExpiry('2026-10-04')).toBe('04.10')
  })
})
