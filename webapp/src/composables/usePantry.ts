import { computed, ref } from 'vue'
import {
  ApiError,
  createPantryItem,
  deletePantryItem,
  getPantry,
  patchPantryItem,
  type PantryChanges,
  type PantryDraft,
  type PantryItem,
  type PantryStatus,
} from '../api/client'
import { haptic } from '../telegram/haptic'
import { SECTION_ORDER, STATUS_LABELS } from '../utils/pantry'
import { useSnackbar } from './useSnackbar'

const DEFAULT_EXPIRY_WARNING_DAYS = 3

const isDuplicate = (error: unknown) => error instanceof ApiError && error.status === 409

export function usePantry() {
  const items = ref<PantryItem[]>([])
  const expiryWarningDays = ref(DEFAULT_EXPIRY_WARNING_DAYS)
  const loading = ref(true)
  const loadError = ref<string | null>(null)
  const snackbar = useSnackbar()

  const sections = computed(() =>
    SECTION_ORDER.map((status) => ({
      status,
      items: items.value.filter((item) => item.status === status),
    })).filter((section) => section.items.length > 0),
  )

  async function load() {
    loading.value = true
    loadError.value = null
    try {
      const data = await getPantry()
      items.value = data.items
      expiryWarningDays.value = data.expiry_warning_days
    } catch (e) {
      loadError.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  /** Вставляет позицию; если сервер вернул уже существующую (дубль названия), заменяет её. */
  function upsert(item: PantryItem) {
    items.value = [...items.value.filter((i) => i.id !== item.id), item].sort((a, b) => a.id - b.id)
  }

  function replace(id: number, next: PantryItem) {
    items.value = items.value.map((i) => (i.id === id ? next : i))
  }

  async function update(id: number, changes: PantryChanges): Promise<boolean> {
    const before = items.value.find((i) => i.id === id)
    if (!before) return false
    replace(id, { ...before, ...changes })
    try {
      replace(id, await patchPantryItem(id, changes))
      haptic.success()
      return true
    } catch (e) {
      replace(id, before)
      haptic.error()
      // дубль названия повтором не исправить: кнопка «Повторить» там бессмысленна
      if (isDuplicate(e)) snackbar.showError('Такая позиция уже есть')
      else snackbar.showError('Не удалось сохранить', () => void update(id, changes))
      return false
    }
  }

  /** Строка уезжает в другую секцию, поэтому сообщаем куда и даём вернуть назад. */
  async function setStatus(item: PantryItem, status: PantryStatus) {
    if (item.status === status) return
    const previous = item.status
    if (await update(item.id, { status })) {
      snackbar.showUndo(
        `${item.name} → ${STATUS_LABELS[status]}`,
        () => void update(item.id, { status: previous }),
      )
    }
  }

  async function add(draft: PantryDraft): Promise<boolean> {
    try {
      upsert(await createPantryItem(draft))
      haptic.success()
      return true
    } catch {
      haptic.error()
      snackbar.showError('Не удалось сохранить', () => void add(draft))
      return false
    }
  }

  /** «Отменить» пересоздаёт позицию с теми же полями (id при этом новый). */
  function restore(item: PantryItem) {
    void add({
      name: item.name,
      status: item.status,
      quantity: item.quantity,
      expiry_date: item.expiry_date,
    })
  }

  function remove(item: PantryItem) {
    items.value = items.value.filter((i) => i.id !== item.id)
    void (async () => {
      try {
        await deletePantryItem(item.id)
        snackbar.showUndo(`Удалено · ${item.name}`, () => restore(item))
      } catch {
        upsert(item)
        haptic.error()
        snackbar.showError('Не удалось удалить', () => remove(item))
      }
    })()
  }

  void load()

  return {
    items,
    sections,
    expiryWarningDays,
    loading,
    loadError,
    setStatus,
    add,
    update,
    remove,
    reload: load,
  }
}
