import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import AppSnackbar from './AppSnackbar.vue'
import { useSnackbar } from '../composables/useSnackbar'

beforeEach(() => {
  useSnackbar().dismiss()
})

describe('AppSnackbar', () => {
  it('ничего не рисует, пока нет сообщения', () => {
    const w = mount(AppSnackbar)
    expect(w.find('[role="alert"]').exists()).toBe(false)
    expect(w.find('[role="status"]').exists()).toBe(false)
  })

  it('ошибка объявляется как alert с кнопкой «Повторить»', async () => {
    const w = mount(AppSnackbar)
    useSnackbar().showError('Не удалось сохранить', () => undefined)
    await w.vm.$nextTick()

    expect(w.get('[role="alert"]').text()).toContain('Не удалось сохранить')
    expect(w.get('button').text()).toBe('Повторить')
  })

  it('удаление объявляется как status с кнопкой «Отменить»', async () => {
    const w = mount(AppSnackbar)
    useSnackbar().showUndo('Удалено · Молоко', () => undefined)
    await w.vm.$nextTick()

    expect(w.get('[role="status"]').text()).toContain('Удалено · Молоко')
    expect(w.get('button').text()).toBe('Отменить')
  })

  it('кнопка вызывает действие и закрывает снекбар', async () => {
    const action = vi.fn()
    const w = mount(AppSnackbar)
    useSnackbar().showError('Ошибка', action)
    await w.vm.$nextTick()

    await w.get('button').trigger('click')

    expect(action).toHaveBeenCalledOnce()
    expect(w.find('[role="alert"]').exists()).toBe(false)
  })
})
