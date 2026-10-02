import { afterEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { bindBackButton } from './backButton'
import { createMockWebApp } from './mock'

const Stub = { template: '<div />' }

function setup() {
  const app = createMockWebApp('x')
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'hub', component: Stub },
      { path: '/settings', name: 'settings', component: Stub },
    ],
  })
  bindBackButton(router, app)
  return { app, router }
}

afterEach(() => {
  delete (window as { __tgMock?: unknown }).__tgMock
})

describe('bindBackButton', () => {
  it('скрыта на хабе', async () => {
    const { app, router } = setup()
    await router.push('/')
    expect(app.BackButton.isVisible).toBe(false)
  })

  it('показана в разделе', async () => {
    const { app, router } = setup()
    await router.push('/settings')
    expect(app.BackButton.isVisible).toBe(true)
  })

  it('нажатие возвращает на хаб', async () => {
    const { router } = setup()
    await router.push('/settings')

    ;(window as unknown as { __tgMock: { pressBack(): void } }).__tgMock.pressBack()
    await router.isReady()
    await new Promise((r) => setTimeout(r))

    expect(router.currentRoute.value.name).toBe('hub')
  })
})
