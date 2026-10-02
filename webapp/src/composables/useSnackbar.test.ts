import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useSnackbar } from './useSnackbar'

beforeEach(() => {
  useSnackbar().dismiss()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('useSnackbar', () => {
  it('изначально пуст', () => {
    expect(useSnackbar().current.value).toBeNull()
  })

  it('showError показывает сообщение с кнопкой «Повторить» и не исчезает сам', () => {
    vi.useFakeTimers()
    const { current, showError } = useSnackbar()

    showError('Не удалось сохранить', () => undefined)
    vi.advanceTimersByTime(60_000)

    expect(current.value).toMatchObject({
      message: 'Не удалось сохранить',
      label: 'Повторить',
      kind: 'error',
    })
  })

  it('showUndo показывает «Отменить» и сам исчезает через 5 секунд', () => {
    vi.useFakeTimers()
    const { current, showUndo } = useSnackbar()

    showUndo('Удалено · Молоко', () => undefined)
    expect(current.value).toMatchObject({ label: 'Отменить', kind: 'undo' })

    vi.advanceTimersByTime(4_999)
    expect(current.value).not.toBeNull()
    vi.advanceTimersByTime(1)
    expect(current.value).toBeNull()
  })

  it('act вызывает переданное действие и закрывает снекбар', () => {
    const { current, showError, act } = useSnackbar()
    const action = vi.fn()

    showError('Ошибка', action)
    act()

    expect(action).toHaveBeenCalledOnce()
    expect(current.value).toBeNull()
  })

  it('dismiss закрывает снекбар без вызова действия', () => {
    const { current, showError, dismiss } = useSnackbar()
    const action = vi.fn()

    showError('Ошибка', action)
    dismiss()

    expect(action).not.toHaveBeenCalled()
    expect(current.value).toBeNull()
  })

  it('новый снекбар заменяет старый и сбрасывает его таймер', () => {
    vi.useFakeTimers()
    const { current, showUndo, showError } = useSnackbar()

    showUndo('Удалено', () => undefined)
    vi.advanceTimersByTime(4_000)
    showError('Ошибка', () => undefined)
    vi.advanceTimersByTime(10_000)

    expect(current.value?.message).toBe('Ошибка')
  })

  it('состояние общее для всех вызовов useSnackbar', () => {
    useSnackbar().showError('Ошибка', () => undefined)
    expect(useSnackbar().current.value?.message).toBe('Ошибка')
  })
})
