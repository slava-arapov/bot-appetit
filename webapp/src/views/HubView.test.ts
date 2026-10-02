import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import type { Summary } from '../api/client'
import HubView from './HubView.vue'

const api = vi.hoisted(() => ({ getSummary: vi.fn() }))
vi.mock('../api/client', () => api)

const summary: Summary = {
  pantry: { total: 5, low: 2, to_buy: 3, expiring: 0 },
  profile: { restrictions: 2, equipment: 3, likes: 3, dislikes: 2 },
  settings: { servings: 4, cooking_time: '30' },
}

beforeEach(() => {
  api.getSummary.mockReset().mockResolvedValue(summary)
})

const mountHub = () => mount(HubView, { global: { stubs: { RouterLink: RouterLinkStub } } })

const cards = (w: ReturnType<typeof mountHub>) =>
  w.findAllComponents(RouterLinkStub).map((link) => ({
    to: link.props('to'),
    title: link.get('[data-test="title"]').text(),
    subtitle: link.find('[data-test="subtitle"]').exists()
      ? link.get('[data-test="subtitle"]').text()
      : null,
  }))

describe('HubView', () => {
  it('показывает три карточки-ссылки', async () => {
    const w = mountHub()
    await flushPromises()
    expect(cards(w).map((c) => [c.to, c.title])).toEqual([
      ['/pantry', 'Запасы'],
      ['/profile', 'Профиль'],
      ['/settings', 'Настройки'],
    ])
  })

  it('подписывает карточки текущим состоянием', async () => {
    const w = mountHub()
    await flushPromises()
    expect(cards(w).map((c) => c.subtitle)).toEqual([
      '2 товара заканчиваются, 3 купить',
      '5 вкусов, 2 ограничения',
      '4 порции · до 30 минут',
    ])
  })

  it('пока сводка грузится, карточки уже работают, а вместо подписей — заглушки', () => {
    api.getSummary.mockReturnValue(new Promise(() => undefined))
    const w = mountHub()
    expect(cards(w)).toHaveLength(3)
    expect(w.findAll('[data-test="subtitle-placeholder"]')).toHaveLength(3)
  })

  it('если сводка не загрузилась, карточки остаются без подписей и без ошибки', async () => {
    api.getSummary.mockRejectedValue(new Error('нет сети'))
    const w = mountHub()
    await flushPromises()

    expect(cards(w).map((c) => c.subtitle)).toEqual([null, null, null])
    expect(w.find('[role="alert"]').exists()).toBe(false)
    expect(w.findAll('[data-test="subtitle-placeholder"]')).toHaveLength(0)
  })

  it('не показывает отладочный user_id', async () => {
    const w = mountHub()
    await flushPromises()
    expect(w.text()).not.toContain('user_id')
  })
})
