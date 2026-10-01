import { getWebApp } from '../telegram'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Authorization', `tma ${getWebApp().initData}`)
  const res = await fetch(path, { ...init, headers })
  if (!res.ok) {
    const detail = await res.json().then(
      (b: { detail?: string }) => b.detail,
      () => undefined,
    )
    throw new ApiError(res.status, detail ?? res.statusText)
  }
  return (await res.json()) as T
}

export interface Me {
  user_id: number
  username: string | null
}

export const getMe = () => apiFetch<Me>('/api/me')
