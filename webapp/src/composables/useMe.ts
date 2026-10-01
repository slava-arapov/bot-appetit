import { onMounted, ref } from 'vue'
import { getMe, type Me } from '../api/client'

export function useMe() {
  const me = ref<Me | null>(null)
  const error = ref<string | null>(null)

  onMounted(async () => {
    try {
      me.value = await getMe()
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    }
  })

  return { me, error }
}
