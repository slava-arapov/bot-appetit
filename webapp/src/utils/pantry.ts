import type { PantryStatus } from '../api/client'

// Единый порядок статусов: секции на экране, лист выбора, форма правки. Что требует внимания — первым.
export const SECTION_ORDER: PantryStatus[] = ['to_buy', 'low', 'have']

export const STATUS_LABELS: Record<PantryStatus, string> = {
  low: 'Мало',
  to_buy: 'Нужно купить',
  have: 'Есть',
}

/** Локальная дата в формате YYYY-MM-DD (toISOString дал бы UTC и сдвиг на сутки около полуночи). */
export function toISODate(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/** Срок годности истекает в пределах окна или уже истёк. */
export function isExpiring(expiry: string | null, warningDays: number, today = new Date()) {
  if (!expiry) return false
  const cutoff = new Date(today.getFullYear(), today.getMonth(), today.getDate() + warningDays)
  return expiry <= toISODate(cutoff)
}

export function formatExpiry(iso: string): string {
  const [, month, day] = iso.split('-')
  return `${day}.${month}`
}
