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
    // у ошибок валидации FastAPI detail — массив, не строка: для него берём statusText
    const detail = await res.json().then(
      (b: { detail?: unknown }) => (typeof b.detail === 'string' ? b.detail : undefined),
      () => undefined,
    )
    throw new ApiError(res.status, detail ?? res.statusText)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export type CookingTime = '15' | '30' | '60' | 'any'

export interface Settings {
  servings: number | null
  cooking_time: CookingTime | null
}

export const getSettings = () => apiFetch<Settings>('/api/settings')

const jsonInit = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const patchSettings = (patch: Partial<Settings>) =>
  apiFetch<Settings>('/api/settings', jsonInit('PATCH', patch))

export type PantryStatus = 'have' | 'low' | 'to_buy'

export interface PantryItem {
  id: number
  name: string
  status: PantryStatus
  quantity: string | null
  expiry_date: string | null
  added_date: string | null
}

export interface PantryResponse {
  items: PantryItem[]
  expiry_warning_days: number
}

export interface PantryDraft {
  name: string
  status?: PantryStatus
  quantity?: string | null
  expiry_date?: string | null
}

export type PantryChanges = Partial<
  Pick<PantryItem, 'name' | 'status' | 'quantity' | 'expiry_date'>
>

export const getPantry = () => apiFetch<PantryResponse>('/api/pantry')

export const createPantryItem = (draft: PantryDraft) =>
  apiFetch<PantryItem>('/api/pantry', jsonInit('POST', draft))

export const patchPantryItem = (id: number, changes: PantryChanges) =>
  apiFetch<PantryItem>(`/api/pantry/${id}`, jsonInit('PATCH', changes))

export const deletePantryItem = (id: number) =>
  apiFetch<void>(`/api/pantry/${id}`, { method: 'DELETE' })

export type TagKind = 'likes' | 'dislikes' | 'restrictions' | 'equipment'

export interface Tag {
  id: number
  value: string
}

export type ProfileResponse = Record<TagKind, Tag[]>

export const getProfile = () => apiFetch<ProfileResponse>('/api/profile')

export const createTag = (kind: TagKind, value: string) =>
  apiFetch<Tag & { kind: TagKind }>('/api/profile/tags', jsonInit('POST', { kind, value }))

export const deleteTag = (id: number) =>
  apiFetch<void>(`/api/profile/tags/${id}`, { method: 'DELETE' })

export interface Summary {
  pantry: { total: number; low: number; to_buy: number; expiring: number }
  profile: Record<TagKind, number>
  settings: Settings
}

export const getSummary = () => apiFetch<Summary>('/api/summary')
