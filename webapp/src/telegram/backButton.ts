import { onScopeDispose, watch, type WatchSource } from 'vue'
import type { Router } from 'vue-router'
import { getWebApp } from './index'
import type { WebApp } from './types'

/** Закрыватели открытых оверлеев: последний открытый — сверху. */
const overlays: Array<() => void> = []

function removeOverlay(close: () => void) {
  const i = overlays.lastIndexOf(close)
  if (i !== -1) overlays.splice(i, 1)
}

/**
 * Пока `open` истинно, «назад» (BackButton Telegram и системная кнопка телефона)
 * закрывает этот оверлей, а не уводит со страницы.
 */
export function useBackClose(open: WatchSource<boolean>, close: () => void) {
  watch(
    open,
    (isOpen) => (isOpen ? overlays.push(close) : removeOverlay(close)),
    { immediate: true },
  )
  onScopeDispose(() => removeOverlay(close))
}

/** BackButton скрыта на хабе, в разделах показана: закрывает оверлей или ведёт обратно на хаб. */
export function bindBackButton(router: Router, app: WebApp = getWebApp()) {
  app.BackButton.onClick(() => {
    const top = overlays[overlays.length - 1]
    if (top) top()
    else void router.push({ name: 'hub' })
  })
  router.afterEach((to) => {
    if (to.name === 'hub') app.BackButton.hide()
    else app.BackButton.show()
  })
}
