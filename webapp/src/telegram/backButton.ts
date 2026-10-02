import type { Router } from 'vue-router'
import { getWebApp } from './index'
import type { WebApp } from './types'

/** BackButton скрыта на хабе, в разделах показана и ведёт обратно на хаб. */
export function bindBackButton(router: Router, app: WebApp = getWebApp()) {
  app.BackButton.onClick(() => void router.push({ name: 'hub' }))
  router.afterEach((to) => {
    if (to.name === 'hub') app.BackButton.hide()
    else app.BackButton.show()
  })
}
