import { describe, expect, it } from 'vitest'
import { router } from './router'

describe('router', () => {
  it('содержит хаб и три раздела', () => {
    const paths = router.getRoutes().map((r) => r.path)
    expect(paths).toEqual(expect.arrayContaining(['/', '/pantry', '/profile', '/settings']))
  })
})
