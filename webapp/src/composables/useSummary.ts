import { ref } from 'vue'
import { getSummary, type Summary } from '../api/client'

/** Сводка для подписей карточек хаба. Ошибка не критична: карточки работают и без подписей. */
export function useSummary() {
  const summary = ref<Summary | null>(null)
  const loading = ref(true)

  async function load() {
    try {
      summary.value = await getSummary()
    } catch {
      summary.value = null
    } finally {
      loading.value = false
    }
  }

  // вызов при создании, а не в onMounted: сводку можно использовать и вне компонента
  void load()

  return { summary, loading, reload: load }
}
