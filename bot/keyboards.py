"""Инлайн-клавиатуры шагов анкеты. Только разметка: логика ответов — в `agent/chef.py` и `bot/handlers.py`.

callback_data: `onb:servings:<n>`, `onb:time:<пресет>`, `onb:eq:<индекс>|other|done`
(лимит Telegram — 64 байта, поэтому техника передаётся индексом из `EQUIPMENT_OPTIONS`).
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from agent.chef import Step
from config import EQUIPMENT_OPTIONS
from memory.store import COOKING_TIME_PRESETS, SERVINGS_RANGE

ONB_PREFIX = "onb:"

COOKING_TIME_LABELS = {"15": "15 мин", "30": "30 мин", "60": "1 час", "any": "Не важно"}

_SERVINGS_PER_ROW = 4
_EQUIPMENT_PER_ROW = 2


def servings_keyboard() -> InlineKeyboardMarkup:
    low, high = SERVINGS_RANGE
    buttons = [
        InlineKeyboardButton(str(n), callback_data=f"{ONB_PREFIX}servings:{n}") for n in range(low, high + 1)
    ]
    return InlineKeyboardMarkup(
        [buttons[i : i + _SERVINGS_PER_ROW] for i in range(0, len(buttons), _SERVINGS_PER_ROW)]
    )


def time_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(COOKING_TIME_LABELS[preset], callback_data=f"{ONB_PREFIX}time:{preset}")
        for preset in COOKING_TIME_PRESETS
    ]])


def equipment_keyboard(selected: set[int]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            f"✅ {name}" if index in selected else name,
            callback_data=f"{ONB_PREFIX}eq:{index}",
        )
        for index, name in enumerate(EQUIPMENT_OPTIONS)
    ]
    rows = [buttons[i : i + _EQUIPMENT_PER_ROW] for i in range(0, len(buttons), _EQUIPMENT_PER_ROW)]
    rows.append([
        InlineKeyboardButton("✏️ Другое", callback_data=f"{ONB_PREFIX}eq:other"),
        InlineKeyboardButton("Готово", callback_data=f"{ONB_PREFIX}eq:done"),
    ])
    return InlineKeyboardMarkup(rows)


def keyboard_for(step: Step | None, selected: set[int] | None = None) -> InlineKeyboardMarkup | None:
    """Клавиатура для шага; None — для текстовых шагов и завершённой анкеты."""
    if step is None:
        return None
    if step.field == "servings":
        return servings_keyboard()
    if step.field == "cooking_time":
        return time_keyboard()
    if step.kind == "multiselect":
        return equipment_keyboard(selected or set())
    return None
