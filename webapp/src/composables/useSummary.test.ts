import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { Summary } from '../api/client'
import { useSummary } from './useSummary'

const api = vi.hoisted(() => ({ getSummary: vi.fn() }))
vi.mock('../api/client', () => api)

const summary: Summary = {
  pantry: { total: 5, low: 1, to_buy: 2, expiring: 0 },
  profile: { restrictions: 1, equipment: 3, likes: 4, dislikes: 1 },
  settings: { servings: 2, cooking_time: '30' },
}

beforeEach(() => {
  api.getSummary.mockReset().mockResolvedValue(summary)
})

describe('useSummary', () => {
  it('загружает сводку при создании', async () => {
    const { summary: data, loading } = useSummary()
    expect(loading.value).toBe(true)
    await flushPromises()
    expect(loading.value).toBe(false)
    expect(data.value).toEqual(summary)
  })

  it('при ошибке не падает: сводки просто нет', async () => {
    api.getSummary.mockRejectedValue(new Error('нет сети'))
    const { summary: data, loading } = useSummary()
    await flushPromises()
    expect(loading.value).toBe(false)
    expect(data.value).toBeNull()
  })
})
