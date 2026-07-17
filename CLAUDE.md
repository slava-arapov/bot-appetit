# CLAUDE.md — Bot Appetit

## Стек

- Python 3.14, async
- `python-telegram-bot` v20+ (PTB) — async Application, не Updater
- `openrouter` Python-пакет — нативный async-клиент для OpenRouter
- `telegramify-markdown` — конвертирует произвольный markdown в валидный MarkdownV2 для Telegram
- Секреты через `.env` + `python-dotenv`

## Архитектура

Монолит с модулями. Никаких фреймворков типа LangChain — всё на чистом Python, чтобы понимать каждый слой.

### Поток при каждом сообщении

```
user message
  → bot/handlers.py       проверка доступа (approved/pending/rejected/new), маршрутизация (онбординг / агент)
  → agent/chef.py         сборка system prompt из памяти конкретного user_id + вызов LLM
  → llm/openrouter.py     вызов OpenRouter через openrouter-пакет (нативный async)
  → agent/chef.py         парсинг JSON-ответа {reply, memory_update}
  → memory/store.py       обновление data/<user_id>/*.json
  → bot/handlers.py       отправка reply с parse_mode=MARKDOWN_V2 (через telegramify_markdown)
```

### Память — JSON-файлы в `data/<user_id>/`

Бот многопользовательский: у каждого Telegram-пользователя своя папка `data/<user_id>/` с одинаковым набором файлов. Все функции в `memory/store.py` принимают `user_id` первым параметром.

| Файл | Что хранит |
|---|---|
| `profile.json` | вкусы, ограничения, техника/посуда (`equipment`), онбординг-статус, текущий контекст |
| `history.json` | список блюд с оценками и датами |
| `context.json` | последние 20 сообщений диалога для LLM |
| `pantry.json` | запасы продуктов: `name`, `status` (have/low/out), `added_date`, опционально `expiry_date` и `quantity` (свободная строка, например "2 пачки") |

Отдельно, на уровне `data/users.json` (не внутри папки пользователя) — общий реестр доступа: `{user_id: {status, username, requested_at/approved_at/rejected_at}}`, см. `memory/users.py`.

`data/` — в `.gitignore`. Бэкапится отдельно через `backup.py` (копирует весь `data/` рекурсивно, включая все подпапки пользователей).

Запасы (`pantry`) и техника (`equipment`) обновляются так же, как остальная память — через `memory_update` от LLM, без отдельных команд бота. Список покупок не хранится отдельно: при предложении рецепта бот сравнивает ингредиенты с `pantry` и называет недостающее прямо в ответе.

Ежедневно в 09:00 `bot/jobs.py:notify_expiring` проходит по всем `approved`-пользователям (`memory/users.py:list_approved_user_ids()`) и для каждого проверяет его `pantry.json` на продукты с `expiry_date` в пределах `EXPIRY_WARNING_DAYS` (см. `config.py`) — детерминированно, без вызова LLM. Регистрируется через `app.job_queue.run_daily(...)` в `main.py` (нужен extra `python-telegram-bot[job-queue]`).

## Ключевые решения

| Решение | Почему |
|---|---|
| JSON-файлы для памяти | Просто, читаемо руками, удобно смотреть/редактировать вручную |
| Structured output от LLM | Обновление памяти и ответ в одном запросе, без цепочек |
| OpenRouter вместо Anthropic API | Pro-подписка Claude не даёт доступ к API |
| `BaseLLMClient` абстракция | Смена провайдера одним классом в `agent/chef.py` |
| `data/` отдельно от кода | Память не смешивается с кодом, легко бэкапить в отдельный репо |
| Мультипользовательский режим с одобрением админом | `ADMIN_USER_ID` из `.env` — единственный, кто approved сразу; остальные после `/start` попадают в `pending` и ждут одобрения через инлайн-кнопки в чате с админом (`memory/users.py`, `bot/handlers.py:handle_approval_callback`) |
| `data/<user_id>/` вместо одного файла на тип данных | Каждого пользователя легко посмотреть/отредактировать отдельно, не задевая остальных |

## Добавление нового LLM-провайдера

1. Создай `llm/myprovider.py`, унаследуйся от `BaseLLMClient`, реализуй `async def chat(...) -> tuple[str, str]` (raw-ответ, имя модели)
2. В `agent/chef.py` замени импорт и инициализацию `_llm`
3. Добавь API-ключ в `.env` и `config.py`

## Известные особенности

- LLM иногда оборачивает JSON в ```json ... ``` или возвращает невалидный JSON. Функция `_extract_json()` в `agent/chef.py` снимает markdown-обёртку; если после этого `json.loads` всё равно падает, `run_agent` повторяет запрос до 3 раз (`_MAX_RETRIES`).
- При отправке в Telegram используется `parse_mode=MARKDOWN_V2`. Текст прогоняется через `telegramify_markdown.markdownify()`, которая экранирует спецсимволы. При `BadRequest` — падбэк на plain text.
- После ответа в конце сообщения добавляется имя модели в виде Telegram-спойлера: `||_model_name_||`.
- `openrouter` пакет имеет нативный async (`send_async`), `asyncio.to_thread()` не нужен.
- Пока LLM думает, хендлер периодически отправляет `ChatAction.TYPING` (`_with_typing` в `bot/handlers.py`).

## Онбординг

Запускается когда `profile.json["onboarding_done"] == false`. Шесть вопросов подряд (включая вопрос про технику/посуду), ответы пишутся в profile. Шаг хранится в `profile["onboarding_step"]`: это индекс+1 вопроса, который уже задан и ждёт ответа (`ONBOARDING_QUESTIONS[onboarding_step - 1]`).

`run_onboarding(user_id, user_message)` при `onboarding_step > 0` трактует `user_message` как ответ на текущий вопрос — поэтому его нельзя дёргать с пустой строкой посреди анкеты (затрёт текущий шаг). Для повторного показа текущего вопроса без сайд-эффектов есть `current_onboarding_question(user_id)` (read-only) — им пользуется `/start`, когда анкета не завершена.

После онбординга все сообщения идут через `run_agent()`.

## Команды бота

Все команды, кроме `/pending` и `/broadcast`, доступны только `approved`-пользователям — гейт `_require_approved()` в `bot/handlers.py`, тот же, что у обычных сообщений (new → заявка в pending, pending → молчим, rejected → однократное уведомление).

| Команда | Кому | Что делает | LLM? |
|---|---|---|---|
| `/start` | все | регистрация нового / повтор текущего вопроса анкеты, если онбординг не завершён / сброс `context.json` + приветствие, если завершён | по ситуации |
| `/cook` | approved | шорткат: шлёт агенту фиксированный промпт «предложи рецепт из pantry», дальше как обычное сообщение (LLM, memory_update) | да |
| `/random` | approved | шорткат: промпт «случайное блюдо-сюрприз с учётом вкусов/ограничений» | да |
| `/pantry` | approved | рендер `pantry.json` по группам have/low/out | нет |
| `/profile` | approved | рендер `profile.json` (вкусы, ограничения, техника) | нет |
| `/reset` | approved | инлайн-меню сброса памяти | нет |
| `/pending` | `ADMIN_USER_ID` | список заявок `pending` с кнопками ✅/❌ | нет |
| `/broadcast <текст>` | `ADMIN_USER_ID` | рассылка всем `approved`-пользователям | нет |

`/cook` и `/random` — не отдельная ветка логики, а просто заготовленный `user_text`, дальше идёт тот же путь, что и у любого сообщения (`_run_agent_reply()` в `bot/handlers.py`). `/pantry` и `/profile` намеренно детерминированные — читают JSON и рендерят напрямую, без похода к LLM.

### `/reset` и подтверждение опасных действий

`/reset` показывает 3 кнопки (`callback_data="reset:chat|onboarding|all"`):
- `reset:chat` — забыть переписку (`context.json`), выполняется сразу, не опасно
- `reset:onboarding` — заполнить анкету заново, **сначала спрашивает подтверждение** (Да/Нет)
- `reset:all` — стереть анкету/историю/контекст/запасы, **сначала спрашивает подтверждение**

Подтверждение — отдельный шаг в `handle_reset_callback`: кнопки Да/Нет шлют `reset_confirm:<action>` / `reset_cancel`. `reset:chat` в этот шаг не попадает — для него в `_DANGEROUS_RESET_ACTIONS` нет записи. Сама логика сброса — в `memory/store.py`: `reset_context`, `reset_onboarding`, `reset_all`. Стоящие отдельными командами `/reset_chat`, `/reset_onboarding`, `/reset_all` намеренно не сделаны — единственная точка входа для сброса это `/reset`, чтобы не тыкать по ошибке в деструктивную команду через автокомплит Telegram.

### Меню команд в Telegram (`/`-подсказки)

Регистрируется в `main.py:_post_init()` через `bot.set_my_commands()`. Обычным пользователям — `DEFAULT_COMMANDS`. Админу — `ADMIN_COMMANDS` (то же плюс `/pending`, `/broadcast`) через `scope=BotCommandScopeChat(chat_id=ADMIN_USER_ID)`: Telegram показывает разное меню в зависимости от того, в каком чате пользователь открыл `/`. Работает только если Telegram уже знает `chat_id` пользователя (т.е. тот хоть раз писал боту) — для админа это не проблема, он лениво регистрируется как `approved` в `users.json` при первом же обращении (`memory/users.py:ensure_approved()`, вызывается из `_resolve_access()`), а не одобряется вручную, как остальные.

### Роутинг `CallbackQueryHandler`

В `main.py` два колбэк-хендлера различаются по `pattern` — без этого первый зарегистрированный ловил бы вообще все inline-нажатия:
- `handle_approval_callback` — `pattern=r"^(approve|reject):"` (одобрение заявок)
- `handle_reset_callback` — `pattern=r"^reset"` (покрывает `reset:`, `reset_confirm:` и `reset_cancel`)

## Переменные окружения

| Переменная | Описание |
|---|---|
| `TELEGRAM_TOKEN` | токен бота от @BotFather |
| `OPENROUTER_API_KEY` | ключ на openrouter.ai/keys |
| `ADMIN_USER_ID` | Telegram user ID владельца (узнать: @userinfobot) |
| `BACKUP_REPO_PATH` | путь к локальному клону приватного репо (опционально) |
