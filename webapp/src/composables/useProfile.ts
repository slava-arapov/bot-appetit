import { ref } from 'vue'
import {
  ApiError,
  createTag,
  deleteTag,
  getProfile,
  type ProfileResponse,
  type Tag,
  type TagKind,
} from '../api/client'
import { haptic } from '../telegram/haptic'
import { normalizeTag, sameValue } from '../utils/profile'
import { useSnackbar } from './useSnackbar'

export function useProfile() {
  const tags = ref<ProfileResponse>({ restrictions: [], equipment: [], likes: [], dislikes: [] })
  const loading = ref(true)
  const loadError = ref<string | null>(null)
  const snackbar = useSnackbar()

  // Отрицательные id у тегов, которые уже показаны, но ещё не подтверждены сервером.
  let pendingId = 0

  async function load(silent = false) {
    if (!silent) loading.value = true
    loadError.value = null
    try {
      tags.value = await getProfile()
    } catch (e) {
      loadError.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  const find = (kind: TagKind, value: string) =>
    tags.value[kind].find((t) => sameValue(t.value, value))

  function setKind(kind: TagKind, list: Tag[]) {
    tags.value = { ...tags.value, [kind]: list }
  }

  async function add(kind: TagKind, rawValue: string): Promise<boolean> {
    const value = normalizeTag(rawValue)
    if (!value) return false
    if (find(kind, value)) return true

    const draft: Tag = { id: --pendingId, value }
    setKind(kind, [...tags.value[kind], draft])
    try {
      const saved = await createTag(kind, value)
      setKind(
        kind,
        tags.value[kind].map((t) => (t.id === draft.id ? { id: saved.id, value: saved.value } : t)),
      )
      haptic.success()
      return true
    } catch {
      setKind(
        kind,
        tags.value[kind].filter((t) => t.id !== draft.id),
      )
      haptic.error()
      snackbar.showError('Не удалось сохранить', () => void add(kind, value))
      return false
    }
  }

  /** undo=false для переключателей: повторный тап по чекбоксу и есть отмена. */
  async function remove(kind: TagKind, tag: Tag, undo = true): Promise<void> {
    setKind(
      kind,
      tags.value[kind].filter((t) => t.id !== tag.id),
    )
    try {
      await deleteTag(tag.id)
      haptic.success()
      if (undo) snackbar.showUndo(`Удалено · ${tag.value}`, () => void add(kind, tag.value))
    } catch (e) {
      // id мог устареть (онбординг пересоздаёт теги): тогда просто подтягиваем актуальный список
      if (e instanceof ApiError && e.status === 404) {
        await load(true)
        return
      }
      setKind(
        kind,
        [...tags.value[kind], tag].sort((a, b) => a.id - b.id),
      )
      haptic.error()
      snackbar.showError('Не удалось удалить', () => void remove(kind, tag, undo))
    }
  }

  async function toggleEquipment(value: string): Promise<void> {
    const existing = find('equipment', value)
    if (existing) await remove('equipment', existing, false)
    else await add('equipment', value)
  }

  void load()

  return { tags, loading, loadError, add, remove, toggleEquipment, reload: load }
}
