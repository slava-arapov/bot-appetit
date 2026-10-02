import { describe, expect, it } from 'vitest'
import { pantrySubtitle, pluralize, profileSubtitle, settingsSubtitle } from './summary'

const WORDS: [string, string, string] = ['товар', 'товара', 'товаров']

describe('pluralize', () => {
  it.each([
    [0, 'товаров'],
    [1, 'товар'],
    [2, 'товара'],
    [4, 'товара'],
    [5, 'товаров'],
    [11, 'товаров'],
    [12, 'товаров'],
    [21, 'товар'],
    [22, 'товара'],
    [25, 'товаров'],
    [111, 'товаров'],
  ])('%i → %s', (count, word) => {
    expect(pluralize(count, WORDS)).toBe(word)
  })
})

describe('pantrySubtitle', () => {
  const pantry = (over: Partial<Record<'total' | 'low' | 'to_buy' | 'expiring', number>>) => ({
    total: 5,
    low: 0,
    to_buy: 0,
    expiring: 0,
    ...over,
  })

  it('пустые запасы', () => {
    expect(pantrySubtitle(pantry({ total: 0 }))).toBe('Пока пусто')
  })

  it('склоняет «заканчивается»', () => {
    expect(pantrySubtitle(pantry({ low: 1 }))).toBe('1 товар заканчивается')
    expect(pantrySubtitle(pantry({ low: 2 }))).toBe('2 товара заканчиваются')
    expect(pantrySubtitle(pantry({ low: 5 }))).toBe('5 товаров заканчиваются')
  })

  it('собирает всё, что требует внимания', () => {
    expect(pantrySubtitle(pantry({ low: 2, to_buy: 3, expiring: 1 }))).toBe(
      '2 товара заканчиваются, 3 купить, 1 скоро испортится',
    )
  })

  it('если ничего не требует внимания, говорит, сколько всего', () => {
    expect(pantrySubtitle(pantry({ total: 7 }))).toBe('В запасах: 7')
  })
})

describe('profileSubtitle', () => {
  const profile = (
    over: Partial<Record<'restrictions' | 'equipment' | 'likes' | 'dislikes', number>>,
  ) => ({
    restrictions: 0,
    equipment: 0,
    likes: 0,
    dislikes: 0,
    ...over,
  })

  it('вкусы — это «любит» и «не любит» вместе', () => {
    expect(profileSubtitle(profile({ likes: 3, dislikes: 2, restrictions: 2 }))).toBe(
      '5 вкусов, 2 ограничения',
    )
  })

  it('склоняет', () => {
    expect(profileSubtitle(profile({ likes: 1, restrictions: 1 }))).toBe('1 вкус, 1 ограничение')
    expect(profileSubtitle(profile({ likes: 2, restrictions: 5 }))).toBe('2 вкуса, 5 ограничений')
  })

  it('без вкусов и ограничений показывает технику', () => {
    expect(profileSubtitle(profile({ equipment: 4 }))).toBe('Техника: 4')
  })

  it('пустой профиль', () => {
    expect(profileSubtitle(profile({}))).toBe('Пока пусто')
  })
})

describe('settingsSubtitle', () => {
  it('порции и время', () => {
    expect(settingsSubtitle({ servings: 4, cooking_time: '30' })).toBe('4 порции · до 30 минут')
  })

  it('«не важно»', () => {
    expect(settingsSubtitle({ servings: null, cooking_time: 'any' })).toBe('время не важно')
  })

  it('только порции', () => {
    expect(settingsSubtitle({ servings: 1, cooking_time: null })).toBe('1 порция')
  })

  it('ничего не задано', () => {
    expect(settingsSubtitle({ servings: null, cooking_time: null })).toBe('Не заданы')
  })
})
