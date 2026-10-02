import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ApiError, type ProfileResponse } from '../api/client'
import { useProfile } from './useProfile'
import { useSnackbar } from './useSnackbar'
import { createMockWebApp } from '../telegram/mock'

const api = vi.hoisted(() => ({
  getProfile: vi.fn(),
  createTag: vi.fn(),
  deleteTag: vi.fn(),
}))
vi.mock('../api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api/client')>()),
  ...api,
}))

const profile = (): ProfileResponse => ({
  restrictions: [{ id: 1, value: 'без глютена' }],
  equipment: [{ id: 2, value: 'духовка' }],
  likes: [{ id: 3, value: 'сыр' }],
  dislikes: [],
})

beforeEach(() => {
  api.getProfile.mockReset().mockImplementation(async () => profile())
  api.createTag
    .mockReset()
    .mockImplementation(async (kind: string, value: string) => ({ id: 100, kind, value }))
  api.deleteTag.mockReset().mockResolvedValue(undefined)
  useSnackbar().dismiss()
  window.Telegram = { WebApp: createMockWebApp('x') }
})

afterEach(() => {
  delete window.Telegram
})

async function ready() {
  const store = useProfile()
  await flushPromises()
  return store
}

const values = (store: Awaited<ReturnType<typeof ready>>, kind: keyof ProfileResponse) =>
  store.tags.value[kind].map((t) => t.value)

describe('useProfile: загрузка', () => {
  it('загружает теги по группам', async () => {
    const store = useProfile()
    expect(store.loading.value).toBe(true)
    await flushPromises()
    expect(store.loading.value).toBe(false)
    expect(values(store, 'likes')).toEqual(['сыр'])
    expect(values(store, 'restrictions')).toEqual(['без глютена'])
  })

  it('при ошибке сохраняет сообщение', async () => {
    api.getProfile.mockRejectedValue(new Error('нет сети'))
    const store = useProfile()
    await flushPromises()
    expect(store.loading.value).toBe(false)
    expect(store.loadError.value).toBe('нет сети')
  })
})

describe('useProfile: добавление', () => {
  it('тег появляется сразу, а потом получает настоящий id', async () => {
    const store = await ready()
    let finish!: (tag: unknown) => void
    api.createTag.mockReturnValueOnce(new Promise((resolve) => (finish = resolve)))

    const done = store.add('dislikes', 'лук')
    expect(values(store, 'dislikes')).toEqual(['лук'])

    finish({ id: 55, kind: 'dislikes', value: 'лук' })
    expect(await done).toBe(true)
    expect(store.tags.value.dislikes).toEqual([{ id: 55, value: 'лук' }])
  })

  it('обрезает пробелы и не шлёт пустое значение', async () => {
    const store = await ready()
    expect(await store.add('likes', '   ')).toBe(false)
    expect(api.createTag).not.toHaveBeenCalled()

    await store.add('likes', '  хлеб ')
    expect(api.createTag).toHaveBeenCalledWith('likes', 'хлеб')
  })

  it('сохраняет тег в нижнем регистре', async () => {
    const store = await ready()
    await store.add('dislikes', ' Лук ')
    expect(api.createTag).toHaveBeenCalledWith('dislikes', 'лук')
    expect(values(store, 'dislikes')).toEqual(['лук'])
  })

  it('дубль без учёта регистра игнорирует, не обращаясь к серверу', async () => {
    const store = await ready()
    expect(await store.add('likes', 'СЫР')).toBe(true)
    expect(api.createTag).not.toHaveBeenCalled()
    expect(values(store, 'likes')).toEqual(['сыр'])
  })

  it('при ошибке убирает тег и предлагает повторить', async () => {
    const store = await ready()
    api.createTag.mockRejectedValueOnce(new Error('сервер недоступен'))

    expect(await store.add('dislikes', 'лук')).toBe(false)
    expect(values(store, 'dislikes')).toEqual([])
    expect(useSnackbar().current.value).toMatchObject({
      message: 'Не удалось сохранить',
      kind: 'error',
    })

    useSnackbar().act()
    await flushPromises()
    expect(values(store, 'dislikes')).toEqual(['лук'])
  })
})

describe('useProfile: удаление', () => {
  it('тег пропадает сразу, на сервер уходит DELETE и появляется «Отменить»', async () => {
    const store = await ready()

    const done = store.remove('likes', store.tags.value.likes[0])
    expect(values(store, 'likes')).toEqual([])
    await done

    expect(api.deleteTag).toHaveBeenCalledWith(3)
    expect(useSnackbar().current.value).toMatchObject({ message: 'Удалено · сыр', kind: 'undo' })
  })

  it('«Отменить» создаёт тег заново', async () => {
    const store = await ready()
    await store.remove('likes', store.tags.value.likes[0])

    useSnackbar().act()
    await flushPromises()

    expect(api.createTag).toHaveBeenCalledWith('likes', 'сыр')
    expect(values(store, 'likes')).toEqual(['сыр'])
  })

  it('если тега уже нет на сервере (404), молча перезапрашивает профиль', async () => {
    const store = await ready()
    api.deleteTag.mockRejectedValueOnce(new ApiError(404, 'Тег не найден'))

    await store.remove('likes', store.tags.value.likes[0])
    await flushPromises()

    expect(api.getProfile).toHaveBeenCalledTimes(2)
    expect(useSnackbar().current.value).toBeNull()
  })

  it('при другой ошибке возвращает тег на место и предлагает повторить', async () => {
    const store = await ready()
    api.deleteTag.mockRejectedValueOnce(new Error('нет сети'))

    await store.remove('likes', store.tags.value.likes[0])

    expect(values(store, 'likes')).toEqual(['сыр'])
    expect(useSnackbar().current.value).toMatchObject({ kind: 'error' })
  })
})

describe('useProfile: чеклист техники', () => {
  it('включение пункта создаёт тег equipment', async () => {
    const store = await ready()
    await store.toggleEquipment('Блендер')
    expect(api.createTag).toHaveBeenCalledWith('equipment', 'блендер')
    expect(values(store, 'equipment')).toContain('блендер')
  })

  it('выключение удаляет тег без «Отменить» (повторный тап и есть отмена)', async () => {
    const store = await ready()
    await store.toggleEquipment('Духовка') // регистр не важен
    expect(api.deleteTag).toHaveBeenCalledWith(2)
    expect(values(store, 'equipment')).toEqual([])
    expect(useSnackbar().current.value).toBeNull()
  })
})
