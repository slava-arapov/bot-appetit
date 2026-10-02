import json
from dataclasses import dataclass
from typing import Literal

import logging
from datetime import date

from config import OPENROUTER_API_KEY, LLM_MODELS, CONTEXT_WINDOW
from llm.openrouter import OpenRouterClient
from memory.store import (
    load_profile, save_profile,
    load_history, load_context, save_context,
    load_pantry, apply_memory_update,
    describe_servings, describe_cooking_time,
    normalize_servings, normalize_cooking_time,
)

logger = logging.getLogger(__name__)

_llm = OpenRouterClient(api_key=OPENROUTER_API_KEY, models=LLM_MODELS)


@dataclass(frozen=True)
class Step:
    """Шаг анкеты. `choice` отвечается кнопкой (или текстом, который распознаёт `normalize_*`),
    `multiselect` — набором кнопок, `text` — свободным текстом через запятую."""

    field: str
    question: str
    kind: Literal["text", "choice", "multiselect"]


@dataclass(frozen=True)
class StepView:
    """Что показать пользователю: `step` — вопрос, ждущий ответа, либо None, когда анкета закончена.
    Клавиатуру по `step.kind` строит слой бота (`bot/keyboards.py`)."""

    text: str
    step: Step | None = None


ONBOARDING_STEPS = [
    Step(
        "likes",
        (
        "Привет! Я Bot Appetit — твой личный шеф-повар 🍳\n\n"
        "Вот что я умею:\n"
        "• Предлагаю рецепты по тому, что есть дома\n"
        "• Составляю план питания на неделю\n"
        "• Даю пошаговые инструкции по готовке\n"
        "• Слежу за запасами — напоминаю, что скоро испортится\n"
        "• Учитываю кухонную технику — не предложу рецепт для суповарки, если её нет\n"
        "• Пишу, что докупить, если чего-то не хватает\n"
        "• Запоминаю вкусы и предпочтения по ходу разговора\n\n"
        "Давай познакомимся. Какие кухни мира тебе нравятся? (итальянская, азиатская, грузинская...)"
        ),
        "text",
    ),
    Step("dislikes", "Что ты точно не ешь или не любишь? (продукты, ингредиенты)", "text"),
    Step("restrictions", "Есть ли диета, аллергии или другие ограничения в еде?", "text"),
    Step("servings", "На сколько человек обычно готовишь?", "choice"),
    Step("cooking_time", "Сколько времени обычно готов тратить на готовку?", "choice"),
    Step(
        "equipment",
        "Какая техника и посуда есть на кухне? Отметь кнопками, а если чего-то нет в списке — нажми «✏️ Другое».",
        "multiselect",
    ),
]

_CHOICE_HINT = "Выбери вариант кнопкой 👇"

_ONBOARDING_DONE = (
    "Отлично, я всё запомнил! 🎉\n\n"
    "Если что-то поменяется, пиши мне в свободной форме: что есть дома, что хочется, сколько есть свободного времени. "
    "Если скажешь, что купил или доел что-то — обновлю запасы. "
    "Когда что-то будет скоро портиться — напомню сам.\n\n"
    "Что приготовим?"
)

SYSTEM_PROMPT_TEMPLATE = """\
Ты — Bot Appetit, персональный шеф-повар пользователя в Telegram.

## Кто ты

Ты шеф с характером и опытом. Готовил в разных странах, пробовал всё, знаешь кухню изнутри. Теперь помогаешь обычным людям есть вкусно — без лекций, без занудства, по-дружески. Общаешься на ты, коротко и по делу. Эмодзи используешь умеренно — только там где они реально добавляют смысл или настроение.

## Что ты умеешь

- Придумываешь рецепты по тому, что есть в холодильнике
- Составляешь план питания на неделю
- Даёшь пошаговые инструкции готовки — чётко и без воды
- Запоминаешь предпочтения пользователя и учитываешь их в следующих ответах
- Следишь за запасами: предлагаешь рецепты так, чтобы первыми использовались продукты, которые скоро испортятся или лежат дольше остальных — не допускаешь, чтобы они портились впустую
- Учитываешь, какая техника и посуда есть у пользователя — не предлагаешь способы готовки под отсутствующее оборудование
- Если для рецепта не хватает каких-то ингредиентов из запасов — прямо говоришь об этом в ответе и называешь, что докупить

## Как ты говоришь

- На ты, по-свойски
- Коротко — не растекаешься текстом без нужды
- Задаёшь уточняющие вопросы прежде чем предлагать — не угадываешь
- Не читаешь лекции о ЗОЖ и правильном питании
- Не осуждаешь вкусы, но своё мнение имеешь
- Если что-то пошло не так на кухне — помогаешь исправить, не осуждаешь
- Если из диалога узнал что-то новое о вкусах — включи в memory_update
- Если из диалога понятно, что пользователь приготовил блюдо и использовал ингредиенты — предложи обновить запасы
- Если узнал, что пользователь что-то купил или принёс домой — обнови pantry в memory_update со status "have" (включая quantity, если знаешь точное количество, например "2 пачки"); если продукт был в списке покупок, он перейдёт в запасы
- Если продукт заканчивается (осталось немного) — status "low"
- Если продукт закончился, его доели или выбросили — status "out": он уберётся из запасов. В том же ответе коротко спроси, добавить ли его в список покупок. Сам в список не добавляй
- Если пользователь согласился добавить продукт в список покупок («да», «добавь», «надо купить») или сам просит записать его в покупки — status "to_buy"
- Продукты со статусом нужно купить (to_buy) — это список покупок, их нет в наличии: при подборе рецепта считай их отсутствующими и называй среди того, что надо докупить
- Если узнал о новой технике/посуде — включи в memory_update.equipment
- Формат рецепта:
* Ингредиенты (список продуктов с количеством)
* Приготовление
* Результат
* Совет (опционально)
- Отвечай только в формате JSON (см. ниже), без markdown-обёрток

## Чего ты не делаешь

- Не навязываешь диеты и не говоришь что вредно
- Не пишешь простыни текста без запроса
- Не притворяешься ассистентом общего назначения — ты про еду

## Дата

Сегодня: {today}. Ориентируйся на эту дату при оценке сроков годности и планировании.

## Память

Вот что ты знаешь о пользователе:
- Любит: {likes}
- Не любит: {dislikes}
- Ограничения: {restrictions}
- Техника и посуда: {equipment}
- Обычно готовит на: {servings}
- Время на готовку: {cooking_time}
- Запасы (от самого срочного к менее срочному): {pantry}
- Текущий контекст: {context_notes}
- Последние блюда: {last_dishes}

## Формат ответа (строго JSON):
{{
  "reply": "текст ответа пользователю",
  "memory_update": {{
    "likes": [],
    "dislikes": [],
    "restrictions": [],
    "equipment": [],
    "pantry": [
      {{"name": "название продукта", "status": "have|low|to_buy|out", "quantity": "2 пачки (опционально)", "expiry_date": "YYYY-MM-DD (опционально)"}}
    ],
    "current_context": "",
    "history": {{
      "dish": "название блюда",
      "rating": "понравилось/не понравилось"
    }}
  }}
}}

Если обновлять нечего — memory_update возвращай как пустой объект {{}}.
"""


def _format_pantry(pantry: list[dict]) -> str:
    if not pantry:
        return "нет данных"

    def sort_key(item):
        return (item.get("expiry_date") or "9999-99-99", item.get("added_date") or "")

    ordered = sorted(pantry, key=sort_key)

    parts = []
    for item in ordered:
        status = item.get("status", "have")
        quantity = f", {item['quantity']}" if item.get("quantity") else ""
        if status == "to_buy":
            parts.append(f"{item['name']} (нужно купить{quantity})")
            continue
        detail = f"годен до {item['expiry_date']}" if item.get("expiry_date") else f"добавлен {item.get('added_date', '?')}"
        parts.append(f"{item['name']} ({status}{quantity}, {detail})")
    return ", ".join(parts)


def build_system_prompt(profile: dict, history: list, pantry: list) -> str:
    last_dishes = history[-5:] if history else []
    dishes_str = ", ".join(
        f"{d['dish']} ({d.get('rating', '?')})" for d in last_dishes
    ) or "нет"

    return SYSTEM_PROMPT_TEMPLATE.format(
        today=date.today().isoformat(),
        likes=", ".join(profile.get("likes", [])) or "не указано",
        dislikes=", ".join(profile.get("dislikes", [])) or "не указано",
        restrictions=", ".join(profile.get("restrictions", [])) or "нет",
        equipment=", ".join(profile.get("equipment", [])) or "не указано",
        servings=describe_servings(profile.get("servings")) or "не указано",
        cooking_time=describe_cooking_time(profile.get("cooking_time")) or "не указано",
        pantry=_format_pantry(pantry),
        context_notes=profile.get("current_context", {}).get("notes") or "нет",
        last_dishes=dishes_str,
    )


def _extract_json(raw: str) -> str:
    """Извлекает JSON-объект из текста: снимает markdown-обёртку, находит {...}."""
    stripped = raw.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        stripped = "\n".join(inner).strip()
    start = stripped.find("{")
    end = stripped.rfind("}") + 1
    if start != -1 and end > start:
        return stripped[start:end]
    return stripped


def parse_response(raw: str) -> tuple[str, dict, bool]:
    try:
        data = json.loads(_extract_json(raw), strict=False)
        reply = data.get("reply") or raw
        memory_update = data.get("memory_update", {})
        return reply, memory_update, True
    except (json.JSONDecodeError, AttributeError, TypeError):
        logger.warning("Не удалось распарсить ответ LLM как JSON: %s", raw[:200])
        return raw, {}, False


_MAX_RETRIES = 3


async def run_agent(user_id: int, user_message: str) -> tuple[str, str | None]:
    profile = await load_profile(user_id)
    history = await load_history(user_id)
    pantry = await load_pantry(user_id)

    system = build_system_prompt(profile, history, pantry)

    messages = await load_context(user_id)
    messages.append({"role": "user", "content": user_message})

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            raw, model_name = await _llm.chat(system=system, messages=messages)
        except Exception as e:
            logger.error("LLM call failed: %s", e, exc_info=True)
            return "Все модели сейчас недоступны, попробуй чуть позже.", None

        reply, memory_update, ok = parse_response(raw)

        if ok:
            break

        logger.warning("Попытка %d/%d: невалидный JSON, перегенерирую.", attempt, _MAX_RETRIES)
        if attempt == _MAX_RETRIES:
            return "Что-то пошло не так, попробуй ещё раз.", None

    messages.append({"role": "assistant", "content": raw})
    await save_context(user_id, messages[-CONTEXT_WINDOW:])

    await apply_memory_update(user_id, memory_update)

    return reply, model_name


def split_items(text: str) -> list[str]:
    return [i.strip() for i in text.replace("\n", ",").split(",") if i.strip()]


def _step_view(step_number: int) -> StepView:
    step = ONBOARDING_STEPS[max(step_number - 1, 0)]
    return StepView(step.question, step)


async def current_onboarding_question(user_id: int) -> StepView:
    """Возвращает уже заданный, но ещё не отвеченный вопрос анкеты, не трогая profile."""
    profile = await load_profile(user_id)
    return _step_view(profile.get("onboarding_step", 0))


async def _submit_answer(user_id: int, profile: dict, answer: str | list[str]) -> StepView:
    """Сохраняет ответ на текущий шаг (если он валиден) и возвращает следующий вопрос.

    Невалидный ответ на `choice` ничего не пишет и не двигает шаг: вопрос показывается повторно.
    """
    step_number = profile.get("onboarding_step", 0)
    if step_number > 0:
        step = ONBOARDING_STEPS[step_number - 1]
        if step.kind == "choice":
            normalize = normalize_servings if step.field == "servings" else normalize_cooking_time
            value = normalize(answer if isinstance(answer, str) else "")
            if value is None:
                return StepView(f"{_CHOICE_HINT}\n\n{step.question}", step)
            profile[step.field] = str(value)
        else:
            profile[step.field] = split_items(answer) if isinstance(answer, str) else list(answer)

    if step_number < len(ONBOARDING_STEPS):
        profile["onboarding_step"] = step_number + 1
        await save_profile(user_id, profile)
        return _step_view(step_number + 1)

    profile["onboarding_done"] = True
    await save_profile(user_id, profile)
    return StepView(_ONBOARDING_DONE)


async def run_onboarding(user_id: int, user_message: str) -> StepView:
    profile = await load_profile(user_id)
    return await _submit_answer(user_id, profile, user_message)


async def apply_onboarding_choice(user_id: int, field: str, value: str | list[str]) -> StepView | None:
    """Ответ кнопкой на шаг `field`. None — кнопка устарела (шаг пройден, анкета закончена или не начата)."""
    profile = await load_profile(user_id)
    step_number = profile.get("onboarding_step", 0)
    if profile.get("onboarding_done") or step_number == 0:
        return None
    if ONBOARDING_STEPS[step_number - 1].field != field:
        return None
    return await _submit_answer(user_id, profile, value)
