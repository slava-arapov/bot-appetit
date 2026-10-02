import { describe, expect, it } from 'vitest'
import { applyScheme } from './index'
import { createMockWebApp } from './mock'

describe('applyScheme', () => {
  it('кладёт схему клиента Telegram в data-scheme корня', () => {
    const root = document.createElement('div')

    applyScheme(createMockWebApp('x', 'dark'), root)
    expect(root.dataset.scheme).toBe('dark')

    applyScheme(createMockWebApp('x', 'light'), root)
    expect(root.dataset.scheme).toBe('light')
  })
})
