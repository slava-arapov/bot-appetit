/** Теги профиля хранятся без пробелов по краям и в нижнем регистре, как и на сервере (`memory/store.py:normalize_tag`). */
export const normalizeTag = (value: string) => value.trim().toLowerCase()

/**
 * Обработчик `input` для полей тегов: переводит введённое в нижний регистр прямо в поле и возвращает значение.
 * Положение курсора сохраняется, иначе правка в середине слова перебрасывала бы его в конец.
 */
export function lowercaseInput(event: Event): string {
  const input = event.target as HTMLInputElement
  const { selectionStart, selectionEnd } = input
  input.value = input.value.toLowerCase()
  if (selectionStart !== null && selectionEnd !== null)
    input.setSelectionRange(selectionStart, selectionEnd)
  return input.value
}

/** «18 окт»: дата обновления заметки бота (`YYYY-MM-DD`); пустая или битая строка — `null`. */
export function formatContextDate(iso: string): string | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso)
  if (!match) return null
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' })
    .format(date)
    .replace('.', '')
}

/** Совпадение значений без учёта регистра и пробелов по краям: «Духовка» и «духовка» — один пункт. */
export const sameValue = (a: string, b: string) => normalizeTag(a) === normalizeTag(b)
