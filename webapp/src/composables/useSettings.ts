import { ref } from 'vue'
import { getSettings, patchSettings, type CookingTime, type Settings } from '../api/client'
import { haptic } from '../telegram/haptic'
import { useSnackbar } from './useSnackbar'

export const SERVINGS_MIN = 1
export const SERVINGS_MAX = 8
const SERVINGS_DEFAULT = 2
const SAVE_DEBOUNCE_MS = 300

export function useSettings() {
  const settings = ref<Settings | null>(null)
  const loading = ref(true)
  const loadError = ref<string | null>(null)
  const snackbar = useSnackbar()

  // Последнее значение, подтверждённое сервером: к нему откатываемся при ошибке сохранения.
  let confirmed: Settings | null = null
  let servingsTimer: ReturnType<typeof setTimeout> | undefined

  async function load() {
    loading.value = true
    loadError.value = null
    try {
      confirmed = await getSettings()
      settings.value = { ...confirmed }
    } catch (e) {
      loadError.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  async function save(patch: Partial<Settings>) {
    try {
      confirmed = await patchSettings(patch)
      haptic.success()
    } catch {
      haptic.error()
      if (settings.value && confirmed) {
        const reverted = Object.fromEntries(
          Object.keys(patch).map((key) => [key, confirmed![key as keyof Settings]]),
        )
        settings.value = { ...settings.value, ...reverted }
      }
      snackbar.showError('Не удалось сохранить', () => apply(patch))
    }
  }

  function apply(patch: Partial<Settings>) {
    if (!settings.value) return
    settings.value = { ...settings.value, ...patch }
    void save(patch)
  }

  function setServings(value: number) {
    if (!settings.value) return
    const servings = Math.min(SERVINGS_MAX, Math.max(SERVINGS_MIN, value))
    settings.value = { ...settings.value, servings }
    clearTimeout(servingsTimer)
    servingsTimer = setTimeout(() => void save({ servings }), SAVE_DEBOUNCE_MS)
  }

  function stepServings(delta: 1 | -1) {
    const current = settings.value?.servings
    setServings(current == null ? SERVINGS_DEFAULT : current + delta)
  }

  function setCookingTime(value: CookingTime) {
    if (settings.value?.cooking_time === value) return
    apply({ cooking_time: value })
  }

  void load()

  return { settings, loading, loadError, setServings, stepServings, setCookingTime, reload: load }
}
