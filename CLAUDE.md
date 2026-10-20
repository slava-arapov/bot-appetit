# CLAUDE.md — Bot Appetit

Подробное устройство (таблицы БД, онбординг, команды, API Mini App, деплой, бэкап) — `docs/architecture.md`. Читай нужный раздел перед правками в соответствующей части. Если поменял поведение, обнови там же.

## Стек

- Python 3.14, async
- `python-telegram-bot` v20+ (PTB) — async Application, не Updater
- `openrouter` Python-пакет — нативный async-клиент для OpenRouter (`send_async`, `asyncio.to_thread()` не нужен)
- `telegramify-markdown` — конвертирует произвольный markdown в валидный MarkdownV2 для Telegram
- SQLite (`aiosqlite`) — вся память бота, один файл `data/bot.db`
- Mini App: FastAPI (`webapp_api/`, внутри процесса бота) + Vue 3/TypeScript/Vite (`webapp/`), UI — выборочно Vant
- Секреты через `.env` + `python-dotenv`

## Архитектура

Монолит с модулями. Никаких фреймворков типа LangChain — всё на чистом Python, чтобы понимать каждый слой.

```
user message
  → bot/handlers.py       проверка доступа (approved/pending/rejected/new), маршрутизация (онбординг / агент)
  → agent/chef.py         сборка system prompt из памяти конкретного user_id + вызов LLM
  → llm/openrouter.py     вызов OpenRouter через openrouter-пакет (нативный async)
  → agent/chef.py         парсинг JSON-ответа {reply, memory_update}
  → memory/store.py       обновление SQLite (data/bot.db)
  → bot/handlers.py       отправка reply с parse_mode=MARKDOWN_V2 (через telegramify_markdown)
```

Схема — `memory/schema.sql`, применяется при старте идемпотентно. Все таблицы содержат `user_id`.

## Правила, которые легко нарушить

- Функции `memory/store.py` и `memory/users.py` — `async def`, `user_id` первым параметром, общее соединение `memory/db.py:get_conn()`. API Mini App ходит через то же соединение.
- Кириллица и регистр: `lower()` в SQLite не понимает кириллицу, поэтому всё делается в Python. Теги профиля пишутся в нижнем регистре (`normalize_tag`), названия продуктов хранятся как есть и сравниваются через `casefold()`.
- Правки из Mini App и от бота — точечные операции с `id` (`add_tag`/`remove_tag`, `add_pantry_item`/`update_pantry_item`/`delete_pantry_item`). `save_profile` (полная перезапись) — только для онбординга и сбросов.
- `memory_update` от LLM: в `pantry` статус `out` не хранится (удаление); `current_context`: строка заменяет, `null` стирает, `""` или отсутствие ключа — не трогает.
- Онбординг: `run_onboarding` при `onboarding_step > 0` считает `user_message` ответом, поэтому с пустой строкой посреди анкеты его не вызывать. Для показа вопроса есть read-only `current_onboarding_question`. `agent/` не импортирует `telegram`, клавиатуры строит `bot/keyboards.py`.
- Порядок `config.EQUIPMENT_OPTIONS` — контракт с уже отправленными клавиатурами (индекс в `callback_data`): новые пункты только в конец.
- Новый `CallbackQueryHandler` — обязательно с `pattern`, иначе он перехватит чужие нажатия.
- Команды, кроме админских, идут через гейт `_require_approved()`. Шорткаты вроде `/cook` — это заготовленный `user_text` для `_run_agent_reply()`, а не отдельная ветка логики.
- Миграции данных (`migrate_*.py`) — разовые, запускаются руками, в CI не входят.

## Проверки

- `pytest` из корня (нужен `requirements-dev.txt`).
- `npm test`, `npm run lint`, `npm run build` — только из `webapp/`. `vitest` из корня не подхватывает конфиг (нет jsdom и Vant) и оставляет пустой `node_modules/.vite`.

## Ключевые решения

| Решение | Почему |
|---|---|
| SQLite вместо JSON-файлов | Растущее число пользователей и связи между сущностями; один процесс на одном VPS — сервер БД не нужен. Подробности — `docs/db-migration.md` |
| Structured output от LLM | Обновление памяти и ответ в одном запросе, без цепочек |
| OpenRouter вместо Anthropic API | Pro-подписка Claude не даёт доступ к API |
| `BaseLLMClient` абстракция | Смена провайдера одним классом в `agent/chef.py` |
| `data/` отдельно от кода | Память не смешивается с кодом, простое расположение для бэкапа |
| Мультипользовательский режим с одобрением админом | `ADMIN_USER_ID` approved сразу, остальные ждут одобрения в `pending` |

## Добавление нового LLM-провайдера

1. Создай `llm/myprovider.py`, унаследуйся от `BaseLLMClient`, реализуй `async def chat(...) -> tuple[str, str]` (raw-ответ, имя модели)
2. В `agent/chef.py` замени импорт и инициализацию `_llm`
3. Добавь API-ключ в `.env` и `config.py`

## Известные особенности

- LLM иногда оборачивает JSON в ```json ... ``` или возвращает невалидный JSON. Функция `_extract_json()` в `agent/chef.py` снимает markdown-обёртку; если после этого `json.loads` всё равно падает, `run_agent` повторяет запрос до 3 раз (`_MAX_RETRIES`).
- При отправке в Telegram используется `parse_mode=MARKDOWN_V2`. Текст прогоняется через `telegramify_markdown.markdownify()`, которая экранирует спецсимволы. При `BadRequest` — фолбэк на plain text.
- После ответа в конце сообщения добавляется имя модели в виде Telegram-спойлера: `||_model_name_||`.
- Пока LLM думает, хендлер периодически отправляет `ChatAction.TYPING` (`_with_typing` в `bot/handlers.py`).
- S3-совместимые хранилища не-AWS: в `backup.py:_backup_s3()` отключены дефолтные контрольные суммы boto3, иначе `XAmzContentSHA256Mismatch`.
- Деплой: nginx не заходит в `/home`, поэтому статику в `/var/www/botappetit` переносит `rsync` в SSH-скрипте.
- Mini App, фронтенд: вне Telegram `telegram-web-app.js` всё равно создаёт `Telegram.WebApp` с пустым `initData`, поэтому mock (`webapp/src/telegram/mock.ts`) включается по пустому `initData`, а не по отсутствию объекта.
- Mini App, доступ: авторизация без dev-обходов, dev-сервер Vite сам подписывает `initData`. Админ становится `approved` лениво, при первом сообщении боту (`ensure_approved`). Пока таблица `users` пуста, `/api/me` отдаёт 403 — сначала напиши тестовому боту.
- Mini App, `id` тегов нестабильны между сессиями (`save_profile` пересоздаёт теги): фронт при 404 тихо перезапрашивает профиль.
- Mini App, UI-библиотека: Vant подключён по компонентам через `unplugin-vue-components` (`webapp/vite.config.ts`); в шаблонах пишутся `<van-skeleton>`, `<van-popup>`, `<van-swipe-cell>` без импортов. В Vitest `vant` приходится пропускать через Vite (`test.server.deps.inline`): иначе Node падает на `.css` из `node_modules`.
- Mini App, тема: `applyTheme` кладёт `themeParams` в `--tg-*`, а `applyScheme` — схему клиента (light/dark) в `data-scheme` на `<html>`. Тема Telegram не равна `prefers-color-scheme`, поэтому цвета статусов запасов переключаются по `[data-scheme='dark']`.
- Mini App, формы: обработчик отправки висит на `@click.prevent` кнопки `type="submit"`, а не на `@submit` формы: jsdom не вызывает `submit` у формы, не прикреплённой к документу, а браузеры превращают Enter в поле в клик по этой кнопке.
- Mini App, API-клиент: `detail` ошибки берётся только если это строка — у 422 FastAPI он массив.
- Mini App, dev-сервер: Vite привязан к `127.0.0.1` (`webapp/vite.config.ts`); API стартует вместе с ботом без флага, поэтому порт `API_PORT` (8080) на машине должен быть свободен, иначе бот падает при старте с `RuntimeError`.
