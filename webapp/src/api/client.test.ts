import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  ApiError,
  apiFetch,
  createPantryItem,
  createTag,
  deletePantryItem,
  deleteTag,
  getPantry,
  getProfile,
  getSettings,
  patchPantryItem,
  patchSettings,
} from './client'
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

  it('при ошибке валидации (detail — не строка) берёт statusText', async () => {
    window.Telegram = { WebApp: createMockWebApp('x') }
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: [{ msg: 'bad' }] }), {
            status: 422,
            statusText: 'Unprocessable Entity',
          }),
      ),
    )
    await expect(apiFetch('/api/x')).rejects.toMatchObject({
      status: 422,
      message: 'Unprocessable Entity',
    })
  })

  it('на 204 возвращает undefined, не пытаясь разобрать JSON', async () => {
    window.Telegram = { WebApp: createMockWebApp('x') }
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(null, { status: 204 })),
    )
    expect(await apiFetch('/api/x', { method: 'DELETE' })).toBeUndefined()
  })
})

describe('settings api', () => {
  it('getSettings читает /api/settings', async () => {
    window.Telegram = { WebApp: createMockWebApp('x') }
    const fetchMock = vi.fn<(path: string, init: RequestInit) => Promise<Response>>(
      async () => new Response(JSON.stringify({ servings: 2, cooking_time: null })),
    )
    vi.stubGlobal('fetch', fetchMock)

    expect(await getSettings()).toEqual({ servings: 2, cooking_time: null })
    expect(fetchMock.mock.calls[0][0]).toBe('/api/settings')
  })

  it('patchSettings шлёт PATCH с JSON-телом', async () => {
    window.Telegram = { WebApp: createMockWebApp('x') }
    const fetchMock = vi.fn<(path: string, init: RequestInit) => Promise<Response>>(
      async () => new Response(JSON.stringify({ servings: 4, cooking_time: null })),
    )
    vi.stubGlobal('fetch', fetchMock)

    await patchSettings({ servings: 4 })
    const init = fetchMock.mock.calls[0][1]
    expect(init.method).toBe('PATCH')
    expect(init.body).toBe(JSON.stringify({ servings: 4 }))
    expect(new Headers(init.headers).get('Content-Type')).toBe('application/json')
  })
})

describe('pantry api', () => {
  const setup = (response: Response) => {
    window.Telegram = { WebApp: createMockWebApp('x') }
    const fetchMock = vi.fn<(path: string, init: RequestInit) => Promise<Response>>(
      async () => response,
    )
    vi.stubGlobal('fetch', fetchMock)
    return fetchMock
  }

  it('getPantry читает /api/pantry', async () => {
    const fetchMock = setup(new Response(JSON.stringify({ items: [], expiry_warning_days: 3 })))
    expect(await getPantry()).toEqual({ items: [], expiry_warning_days: 3 })
    expect(fetchMock.mock.calls[0][0]).toBe('/api/pantry')
  })

  it('createPantryItem шлёт POST с JSON-телом', async () => {
    const fetchMock = setup(new Response(JSON.stringify({ id: 1 })))
    await createPantryItem({ name: 'Молоко', status: 'to_buy' })
    const [path, init] = fetchMock.mock.calls[0]
    expect(path).toBe('/api/pantry')
    expect(init.method).toBe('POST')
    expect(init.body).toBe(JSON.stringify({ name: 'Молоко', status: 'to_buy' }))
  })

  it('patchPantryItem шлёт PATCH на /api/pantry/{id}', async () => {
    const fetchMock = setup(new Response(JSON.stringify({ id: 5 })))
    await patchPantryItem(5, { quantity: null })
    const [path, init] = fetchMock.mock.calls[0]
    expect(path).toBe('/api/pantry/5')
    expect(init.method).toBe('PATCH')
    expect(init.body).toBe(JSON.stringify({ quantity: null }))
  })

  it('deletePantryItem шлёт DELETE и переживает пустой ответ', async () => {
    const fetchMock = setup(new Response(null, { status: 204 }))
    expect(await deletePantryItem(5)).toBeUndefined()
    const [path, init] = fetchMock.mock.calls[0]
    expect(path).toBe('/api/pantry/5')
    expect(init.method).toBe('DELETE')
  })
})

describe('profile api', () => {
  const setup = (response: Response) => {
    window.Telegram = { WebApp: createMockWebApp('x') }
    const fetchMock = vi.fn<(path: string, init: RequestInit) => Promise<Response>>(
      async () => response,
    )
    vi.stubGlobal('fetch', fetchMock)
    return fetchMock
  }

  it('getProfile читает /api/profile', async () => {
    const body = { restrictions: [], equipment: [], likes: [], dislikes: [] }
    const fetchMock = setup(new Response(JSON.stringify(body)))
    expect(await getProfile()).toEqual(body)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/profile')
  })

  it('createTag шлёт POST с видом и значением', async () => {
    const fetchMock = setup(new Response(JSON.stringify({ id: 1 })))
    await createTag('likes', 'сыр')
    const [path, init] = fetchMock.mock.calls[0]
    expect(path).toBe('/api/profile/tags')
    expect(init.method).toBe('POST')
    expect(init.body).toBe(JSON.stringify({ kind: 'likes', value: 'сыр' }))
  })

  it('deleteTag шлёт DELETE и переживает пустой ответ', async () => {
    const fetchMock = setup(new Response(null, { status: 204 }))
    expect(await deleteTag(7)).toBeUndefined()
    const [path, init] = fetchMock.mock.calls[0]
    expect(path).toBe('/api/profile/tags/7')
    expect(init.method).toBe('DELETE')
  })
})
