import json

import logging

from config import OPENROUTER_API_KEY, LLM_MODELS, CONTEXT_WINDOW
from llm.openrouter import OpenRouterClient
from memory.store import (
    load_profile, save_profile,
    load_history, load_context, save_context,
    apply_memory_update,
)

logger = logging.getLogger(__name__)

_llm = OpenRouterClient(api_key=OPENROUTER_API_KEY, models=LLM_MODELS)

ONBOARDING_QUESTIONS = [
    "Привет! Я твой личный шеф-повар 🍳 Давай познакомимся. Какие кухни мира тебе нравятся? (например: итальянская, азиатская, грузинская)",
    "Отлично! Что ты точно не ешь или не любишь? (продукты, ингредиенты)",
    "Есть ли у тебя диета, аллергии или другие ограничения в еде?",
    "На сколько человек ты обычно готовишь?",
    "Сколько времени ты обычно готов тратить на готовку? (например: до 30 минут, 1 час, не важно)",
]

ONBOARDING_FIELDS = ["likes", "dislikes", "restrictions", "servings", "cooking_time"]

SYSTEM_PROMPT_TEMPLATE = """\
Ты — Bot Appetit, персональный шеф-повар пользователя в Telegram.

## Кто ты

Ты шеф с характером и опытом. Готовил в разных странах, пробовал всё, знаешь кухню изнутри. Теперь помогаешь обычным людям есть вкусно — без лекций, без занудства, по-дружески. Общаешься на ты, коротко и по делу. Эмодзи используешь умеренно — только там где они реально добавляют смысл или настроение.

## Что ты умеешь

- Придумываешь рецепты по тому что есть в холодильнике
- Составляешь план питания на неделю
- Даёшь пошаговые инструкции готовки — чётко и без воды
- Запоминаешь предпочтения пользователя и учитываешь их в следующих ответах

## Как ты говоришь

- На ты, по-свойски
- Коротко — не растекаешься текстом без нужды
- Задаёшь уточняющие вопросы прежде чем предлагать — не угадываешь
- Не читаешь лекции о ЗОЖ и правильном питании
- Не осуждаешь вкусы, но своё мнение имеешь
- Если что-то пошло не так на кухне — помогаешь исправить, не осуждаешь
- Если из диалога узнал что-то новое о вкусах — включи в memory_update
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

## Память

Вот что ты знаешь о пользователе:
- Любит: {likes}
- Не любит: {dislikes}
- Ограничения: {restrictions}
- Текущий контекст: {context_notes}
- Последние блюда: {last_dishes}

## Формат ответа (строго JSON):
{{
  "reply": "текст ответа пользователю",
  "memory_update": {{
    "likes": [],
    "dislikes": [],
    "restrictions": [],
    "current_context": "",
    "history": {{
      "dish": "название блюда",
      "rating": "понравилось/не понравилось"
    }}
  }}
}}

Если обновлять нечего — memory_update возвращай как пустой объект {{}}.
"""


def build_system_prompt(profile: dict, history: list) -> str:
    last_dishes = history[-5:] if history else []
    dishes_str = ", ".join(
        f"{d['dish']} ({d.get('rating', '?')})" for d in last_dishes
    ) or "нет"

    return SYSTEM_PROMPT_TEMPLATE.format(
        likes=", ".join(profile.get("likes", [])) or "не указано",
        dislikes=", ".join(profile.get("dislikes", [])) or "не указано",
        restrictions=", ".join(profile.get("restrictions", [])) or "нет",
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


def parse_response(raw: str) -> tuple[str, dict]:
    try:
        data = json.loads(_extract_json(raw))
        reply = data.get("reply") or raw
        memory_update = data.get("memory_update", {})
        return reply, memory_update
    except (json.JSONDecodeError, AttributeError, TypeError):
        logger.warning("Не удалось распарсить ответ LLM как JSON: %s", raw[:200])
        return raw, {}


async def run_agent(user_message: str) -> tuple[str, str | None]:
    profile = load_profile()
    history = load_history()

    system = build_system_prompt(profile, history)

    messages = load_context()
    messages.append({"role": "user", "content": user_message})

    try:
        raw, model_name = await _llm.chat(system=system, messages=messages)
    except Exception as e:
        logger.error("LLM call failed: %s", e, exc_info=True)
        return "Все модели сейчас недоступны, попробуй чуть позже.", None

    reply, memory_update = parse_response(raw)

    messages.append({"role": "assistant", "content": raw})
    save_context(messages[-CONTEXT_WINDOW:])

    apply_memory_update(memory_update)

    return reply, model_name


async def run_onboarding(user_message: str) -> str:
    profile = load_profile()
    step = profile.get("onboarding_step", 0)

    # Сохранить ответ на текущий шаг (кроме первого приветствия)
    if step > 0:
        field = ONBOARDING_FIELDS[step - 1]
        if field in ("likes", "dislikes", "restrictions"):
            # Разбиваем ответ на список (через запятую или перенос строки)
            items = [i.strip() for i in user_message.replace("\n", ",").split(",") if i.strip()]
            profile[field] = items
        else:
            profile[field] = user_message

    # Переход на следующий шаг
    if step < len(ONBOARDING_QUESTIONS):
        question = ONBOARDING_QUESTIONS[step]
        profile["onboarding_step"] = step + 1
        save_profile(profile)
        return question
    else:
        # Онбординг завершён
        profile["onboarding_done"] = True
        save_profile(profile)
        return (
            "Отлично, я всё запомнил! Теперь я готов помогать тебе с готовкой. "
            "Что приготовим?"
        )
