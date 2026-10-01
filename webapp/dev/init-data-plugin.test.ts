import { describe, expect, it } from 'vitest'
import { signInitData } from './init-data-plugin'

describe('signInitData', () => {
  const user = { id: 42, first_name: 'Dev', username: 'dev' }

  it('содержит user, auth_date и hash', () => {
    const params = new URLSearchParams(signInitData('1:TOKEN', user, 1700000000))
    expect(JSON.parse(params.get('user')!)).toEqual(user)
    expect(params.get('auth_date')).toBe('1700000000')
    expect(params.get('hash')).toMatch(/^[0-9a-f]{64}$/)
  })

  it('детерминирован и зависит от токена', () => {
    const a = signInitData('1:TOKEN', user, 1700000000)
    expect(signInitData('1:TOKEN', user, 1700000000)).toBe(a)
    expect(signInitData('2:OTHER', user, 1700000000)).not.toBe(a)
  })
})
