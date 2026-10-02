import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import type { ProfileResponse } from '../api/client'
import ProfileView from './ProfileView.vue'
import { useSnackbar } from '../composables/useSnackbar'
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
  restrictions: [],
  equipment: [{ id: 2, value: 'духовка' }],
  likes: [{ id: 3, value: 'сыр' }],
  dislikes: [],
  equipment_options: ['духовка', 'плита', 'блендер'],
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

async function mountView() {
  const w = mount(ProfileView)
  await flushPromises()
  return w
}

describe('ProfileView', () => {
  it('пока идёт загрузка, показывает скелетон', () => {
    api.getProfile.mockReturnValue(new Promise(() => undefined))
    const w = mount(ProfileView)
    expect(w.find('.van-skeleton').exists()).toBe(true)
  })

  it('показывает четыре группы в порядке: ограничения, техника, любит, не любит', async () => {
    const w = await mountView()
    expect(w.findAll('h2').map((h) => h.text())).toEqual([
      'Ограничения',
      'Техника и посуда',
      'Любит',
      'Не любит',
    ])
  })

  it('чек-лист техники строится из списка, пришедшего с сервера', async () => {
    const w = await mountView()
    const items = w.findAll('section')[1].findAll('[data-test="item"]')
    expect(items.map((i) => i.text())).toEqual(['духовка', 'плита', 'блендер'])
  })

  it('добавление тега в «Не любит» сохраняет его', async () => {
    const w = await mountView()
    const dislikes = w.findAll('section')[3]

    await dislikes.get('[data-test="input"]').setValue('лук')
    await dislikes.get('[data-test="add"]').trigger('click')
    await flushPromises()

    expect(api.createTag).toHaveBeenCalledWith('dislikes', 'лук')
    expect(dislikes.text()).toContain('лук')
  })

  it('удаление тега показывает «Удалено · …» с отменой', async () => {
    const w = await mountView()
    await w.get('[aria-label="Удалить сыр"]').trigger('click')
    await flushPromises()

    expect(api.deleteTag).toHaveBeenCalledWith(3)
    expect(useSnackbar().current.value?.message).toBe('Удалено · сыр')
  })

  it('чеклист: включение пункта техники сохраняет его', async () => {
    const w = await mountView()
    const blender = w.findAll('[data-test="item"]').find((i) => i.text() === 'блендер')!
    await blender.get('input').trigger('change')
    await flushPromises()

    expect(api.createTag).toHaveBeenCalledWith('equipment', 'блендер')
  })

  it('при ошибке загрузки показывает сообщение и «Повторить»', async () => {
    api.getProfile.mockRejectedValueOnce(new Error('нет сети'))
    const w = await mountView()

    expect(w.text()).toContain('Не удалось загрузить профиль')
    await w.get('[data-test="reload"]').trigger('click')
    await flushPromises()

    expect(w.text()).toContain('сыр')
  })
})
