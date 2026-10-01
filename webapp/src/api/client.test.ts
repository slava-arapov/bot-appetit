import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiFetch } from './client'
import { createMockWebApp } from '../telegram/mock'

afterEach(() => {
  delete window.Telegram
  vi.unstubAllGlobals()
})

describe('apiFetch', () => {
  it('отправляет Authorization: tma <initData>', async () => {
    window.Telegram = { WebApp: createMockWebApp('signed-data') }
    const fetchMock = vi.fn<(path: string, init: RequestInit) => Promise<Response>>(
      async () => new Response(JSON.stringify({ ok: 1 })),
    )
    vi.stubGlobal('fetch', fetchMock)

    expect(await apiFetch('/api/x')).toEqual({ ok: 1 })
    const init = fetchMock.mock.calls[0][1]
    expect(new Headers(init.headers).get('Authorization')).toBe('tma signed-data')
  })

  it('бросает ApiError со статусом и detail из ответа', async () => {
    window.Telegram = { WebApp: createMockWebApp('x') }
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ detail: 'нет доступа' }), { status: 403 })),
    )
    await expect(apiFetch('/api/x')).rejects.toMatchObject({
      status: 403,
      message: 'нет доступа',
    })
    await expect(apiFetch('/api/x')).rejects.toBeInstanceOf(ApiError)
  })
})
