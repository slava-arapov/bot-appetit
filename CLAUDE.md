# CLAUDE.md — Bot Appetit

## Стек

- Python 3.14, async
- `python-telegram-bot` v20+ (PTB) — async Application, не Updater
- `openai` SDK с `base_url="https://openrouter.ai/api/v1"` — OpenRouter-совместимый API
- Секреты через `.env` + `python-dotenv`

## Архитектура

Монолит с модулями. Никаких фреймворков типа LangChain — всё на чистом Python, чтобы понимать каждый слой.

### Поток при каждом сообщении

```
user message
  → bot/handlers.py       проверка admin, маршрутизация (онбординг / агент)
  → agent/chef.py         сборка system prompt из памяти + вызов LLM
  → llm/openrouter.py     HTTP-запрос к OpenRouter
  → agent/chef.py         парсинг JSON-ответа {reply, memory_update}
  → memory/store.py       обновление data/*.json
  → bot/handlers.py       отправка reply с parse_mode=MARKDOWN
```

### Память — JSON-файлы в `data/`

| Файл | Что хранит |
|---|---|
| `profile.json` | вкусы, ограничения, техника/посуда (`equipment`), онбординг-статус, текущий контекст |
| `history.json` | список блюд с оценками и датами |
| `context.json` | последние 20 сообщений диалога для LLM |
| `pantry.json` | запасы продуктов: `name`, `status` (have/low/out), `added_date`, опционально `expiry_date` и `quantity` (свободная строка, например "2 пачки") |

`data/` — в `.gitignore`. Бэкапится отдельно через `backup.py`.

Запасы (`pantry`) и техника (`equipment`) обновляются так же, как остальная память — через `memory_update` от LLM, без отдельных команд бота. Список покупок не хранится отдельно: при предложении рецепта бот сравнивает ингредиенты с `pantry` и называет недостающее прямо в ответе.

Ежедневно в 09:00 `bot/jobs.py:notify_expiring` проверяет `pantry.json` на продукты с `expiry_date` в пределах `EXPIRY_WARNING_DAYS` (см. `config.py`) и шлёт уведомление — детерминированно, без вызова LLM. Регистрируется через `app.job_queue.run_daily(...)` в `main.py` (нужен extra `python-telegram-bot[job-queue]`).

## Ключевые решения

| Решение | Почему |
|---|---|
| JSON-файлы для памяти | Просто, читаемо руками, удобно смотреть/редактировать вручную |
| Structured output от LLM | Обновление памяти и ответ в одном запросе, без цепочек |
| OpenRouter вместо Anthropic API | Pro-подписка Claude не даёт доступ к API |
| `BaseLLMClient` абстракция | Смена провайдера одним классом в `agent/chef.py` |
| `data/` отдельно от кода | Память не смешивается с кодом, легко бэкапить в отдельный репо |
| Бот только для одного пользователя | `ADMIN_USER_ID` в `.env`, все чужие сообщения игнорируются молча |

## Добавление нового LLM-провайдера

1. Создай `llm/myprovider.py`, унаследуйся от `BaseLLMClient`, реализуй `async def chat(...) -> str`
2. В `agent/chef.py` замени импорт и инициализацию `_llm`
3. Добавь API-ключ в `.env` и `config.py`

## Известные особенности

- LLM иногда оборачивает JSON в ```json ... ```. Функция `_strip_markdown_json()` в `agent/chef.py` это обрабатывает.
- При отправке в Telegram используется `parse_mode=MARKDOWN` (legacy, не MarkdownV2). Если модель генерирует невалидный markdown — падбэк на plain text.
- `asyncio.to_thread()` используется для вызова синхронного `openai` SDK из async-кода.

## Онбординг

Запускается когда `profile.json["onboarding_done"] == false`. Шесть вопросов подряд (включая вопрос про технику/посуду), ответы пишутся в profile. Шаг хранится в `profile["onboarding_step"]`.

После онбординга все сообщения идут через `run_agent()`.

## Переменные окружения

| Переменная | Описание |
|---|---|
| `TELEGRAM_TOKEN` | токен бота от @BotFather |
| `OPENROUTER_API_KEY` | ключ на openrouter.ai/keys |
| `ADMIN_USER_ID` | Telegram user ID владельца (узнать: @userinfobot) |
| `BACKUP_REPO_PATH` | путь к локальному клону приватного репо (опционально) |