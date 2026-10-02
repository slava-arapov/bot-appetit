import type { Settings, Summary } from '../api/client'

/** Склонение по числу: pluralize(2, ['товар', 'товара', 'товаров']) → «товара». */
export function pluralize(count: number, [one, few, many]: [string, string, string]): string {
  const lastTwo = count % 100
  const last = count % 10
  if (last === 1 && lastTwo !== 11) return one
  if (last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14)) return few
  return many
}

export function pantrySubtitle({ total, low, to_buy, expiring }: Summary['pantry']): string {
  if (total === 0) return 'Пока пусто'

  const parts: string[] = []
  if (low > 0) {
    const goods = pluralize(low, ['товар', 'товара', 'товаров'])
    const running = pluralize(low, ['заканчивается', 'заканчиваются', 'заканчиваются'])
    parts.push(`${low} ${goods} ${running}`)
  }
  if (to_buy > 0) parts.push(`${to_buy} купить`)
  if (expiring > 0) {
    const spoil = pluralize(expiring, ['скоро испортится', 'скоро испортятся', 'скоро испортятся'])
    parts.push(`${expiring} ${spoil}`)
  }
  return parts.length > 0 ? parts.join(', ') : `В запасах: ${total}`
}

export function profileSubtitle(profile: Summary['profile']): string {
  const tastes = profile.likes + profile.dislikes
  const parts: string[] = []
  if (tastes > 0) parts.push(`${tastes} ${pluralize(tastes, ['вкус', 'вкуса', 'вкусов'])}`)
  if (profile.restrictions > 0) {
    const word = pluralize(profile.restrictions, ['ограничение', 'ограничения', 'ограничений'])
    parts.push(`${profile.restrictions} ${word}`)
  }
  if (parts.length > 0) return parts.join(', ')
  return profile.equipment > 0 ? `Техника: ${profile.equipment}` : 'Пока пусто'
}

export function settingsSubtitle({ servings, cooking_time }: Settings): string {
  const parts: string[] = []
  if (servings !== null)
    parts.push(`${servings} ${pluralize(servings, ['порция', 'порции', 'порций'])}`)
  if (cooking_time !== null)
    parts.push(cooking_time === 'any' ? 'время не важно' : `до ${cooking_time} минут`)
  return parts.length > 0 ? parts.join(' · ') : 'Не заданы'
}
