import { shallowRef } from 'vue'

export interface Snack {
  message: string
  /** Подпись кнопки: «Повторить» для ошибки, «Отменить» для удаления. */
  label: string
  kind: 'error' | 'undo'
  action: () => void
}

const UNDO_VISIBLE_MS = 5000

// Состояние общее на всё приложение: один снекбар, его рисует App.vue.
const current = shallowRef<Snack | null>(null)
let timer: ReturnType<typeof setTimeout> | undefined

function dismiss() {
  clearTimeout(timer)
  current.value = null
}

function show(snack: Snack, autoDismissMs?: number) {
  clearTimeout(timer)
  current.value = snack
  if (autoDismissMs) timer = setTimeout(dismiss, autoDismissMs)
}

export function useSnackbar() {
  /** Ошибка не исчезает сама: изменение не должно теряться незаметно. Без action — кнопка «Понятно». */
  function showError(message: string, action?: () => void) {
    show({
      message,
      kind: 'error',
      label: action ? 'Повторить' : 'Понятно',
      action: action ?? dismiss,
    })
  }

  /** Сообщение об удалении с «Отменить»; исчезает через несколько секунд. */
  function showUndo(message: string, undo: () => void) {
    show({ message, kind: 'undo', label: 'Отменить', action: undo }, UNDO_VISIBLE_MS)
  }

  /** Нажатие кнопки снекбара: закрывает его и выполняет действие. */
  function act() {
    const snack = current.value
    dismiss()
    snack?.action()
  }

  return { current, showError, showUndo, dismiss, act }
}
