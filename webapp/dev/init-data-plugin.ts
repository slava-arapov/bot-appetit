import { createHmac } from 'node:crypto'
import type { Plugin } from 'vite'
import { loadEnv } from 'vite'

/** Подписывает initData по алгоритму Telegram Mini Apps (независимо от Python-проверки в API). */
export function signInitData(
  botToken: string,
  user: { id: number; first_name: string; username?: string },
  authDate: number = Math.floor(Date.now() / 1000),
): string {
  const fields: Record<string, string> = {
    auth_date: String(authDate),
    user: JSON.stringify(user),
  }
  const checkString = Object.keys(fields)
    .sort()
    .map((k) => `${k}=${fields[k]}`)
    .join('\n')
  const secret = createHmac('sha256', 'WebAppData').update(botToken).digest()
  const hash = createHmac('sha256', secret).update(checkString).digest('hex')
  return new URLSearchParams({ ...fields, hash }).toString()
}

/**
 * Dev-only: отдаёт свежий подписанный initData по /__dev/init-data.
 * Токен и ADMIN_USER_ID читаются из ../.env и остаются в процессе Node;
 * плагин работает только в `vite serve`, в сборку не попадает.
 */
export function devInitData(): Plugin {
  return {
    name: 'dev-init-data',
    apply: 'serve',
    configureServer(server) {
      const env = loadEnv(server.config.mode, '..', '')
      server.middlewares.use('/__dev/init-data', (_req, res) => {
        const token = env.TELEGRAM_TOKEN
        const userId = Number(env.ADMIN_USER_ID)
        if (!token || !userId) {
          res.statusCode = 500
          res.end('Нужны TELEGRAM_TOKEN и ADMIN_USER_ID в ../.env')
          return
        }
        res.setHeader('Content-Type', 'text/plain; charset=utf-8')
        res.setHeader('Cache-Control', 'no-store')
        res.end(signInitData(token, { id: userId, first_name: 'Dev', username: 'dev' }))
      })
    },
  }
}
