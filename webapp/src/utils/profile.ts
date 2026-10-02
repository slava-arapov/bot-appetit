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

// Частая техника и посуда для чеклиста; всё остальное пользователь добавляет сам («+ своё»).
export const DEFAULT_EQUIPMENT = [
  'духовка',
  'плита',
  'микроволновка',
  'мультиварка',
  'аэрогриль',
  'блендер',
  'миксер',
  'кухонный комбайн',
  'мясорубка',
  'хлебопечь',
  'пароварка',
  'гриль',
]

/** Совпадение значений без учёта регистра и пробелов по краям: «Духовка» и «духовка» — один пункт. */
export const sameValue = (a: string, b: string) => normalizeTag(a) === normalizeTag(b)
