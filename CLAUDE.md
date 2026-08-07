# CLAUDE.md — Bot Appetit

## Стек

- Python 3.14, async
- `python-telegram-bot` v20+ (PTB) — async Application, не Updater
- `openrouter` Python-пакет — нативный async-клиент для OpenRouter
- `telegramify-markdown` — конвертирует произвольный markdown в валидный MarkdownV2 для Telegram
- SQLite (`aiosqlite`) — вся память бота, один файл `data/bot.db`
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
  → memory/store.py       обновление SQLite (data/bot.db)
  → bot/handlers.py       отправка reply с parse_mode=MARKDOWN_V2 (через telegramify_markdown)
```

### Память — SQLite (`data/bot.db`)

Бот многопользовательский: все таблицы содержат `user_id` (Telegram id) и хранят строки всех пользователей вместе — не отдельные файлы на человека, как было раньше. Все функции в `memory/store.py` и `memory/users.py` — `async def`, принимают `user_id` первым параметром, работают через общее соединение `aiosqlite` из `memory/db.py` (открывается при старте бота в `main.py:_post_init`, схема — `memory/schema.sql`, применяется идемпотентно `CREATE TABLE IF NOT EXISTS`).

| Таблица | Что хранит |
|---|---|
| `profiles` + `profile_tags` | вкусы/ограничения/техника (`profile_tags`, kind = likes/dislikes/restrictions/equipment), `servings`, `cooking_time`, онбординг-статус, текущий контекст |
| `history` | блюда с оценками и датами |
| `context_messages` | последние 20 сообщений диалога для LLM |
| `pantry_items` | запасы продуктов: `name`, `status` (have/low/out), `added_date`, опционально `expiry_date` и `quantity` (свободная строка, например "2 пачки") |
| `users` | реестр доступа (status/username/requested_at/approved_at/rejected_at), см. `memory/users.py` — раньше был отдельным `data/users.json` |
| `stats` | счётчики вызовов команд (key/value), см. `memory/stats.py` |

`data/` (вместе с `bot.db`) — в `.gitignore`. Бэкапится через `backup.py`: ежедневный консистентный снапшот (`VACUUM INTO`) → gzip → S3 или git-репо, см. раздел «Бэкап памяти» ниже.

Почему SQLite, а не JSON-файлы или полноценный сервер БД (Postgres) — см. Decision Log в `docs/db-migration.md`. Переход с JSON выполнен разовым скриптом `migrate_to_sqlite.py` (запускается вручную, ничего не удаляет — легаси `data/<user_id>/*.json` стирается вручную после проверки).

Запасы (`pantry_items`) и техника (`equipment`) обновляются так же, как остальная память — через `memory_update` от LLM, без отдельных команд бота. Список покупок не хранится отдельно: при предложении рецепта бот сравнивает ингредиенты с `pantry_items` и называет недостающее прямо в ответе.

Ежедневно в 09:00 `bot/jobs.py:notify_expiring` проходит по всем `approved`-пользователям (`memory/users.py:list_approved_user_ids()`) и для каждого проверяет его запасы (`memory/store.py:check_expiring_soon`) на продукты с `expiry_date` в пределах `EXPIRY_WARNING_DAYS` (см. `config.py`) — детерминированно, без вызова LLM. Регистрируется через `app.job_queue.run_daily(...)` в `main.py` (нужен extra `python-telegram-bot[job-queue]`).

### Бэкап памяти

`backup.py` — отдельный процесс (свой systemd-сервис), не часть основного бота. Ежедневно в 03:00: `VACUUM INTO` консистентный снапшот `data/bot.db` → gzip → отправка в backend, выбираемый `BACKUP_BACKEND`:

- `s3` (по умолчанию) — `_backup_s3()`, через `boto3` в `S3_BUCKET`/`S3_PREFIX`, хранит последние `BACKUP_RETENTION_DAYS` (14) снапшотов, старые удаляет.
- `git` (опция) — `_backup_git()`, коммитит и перезаписывает один файл `bot.db.gz` в приватном репо (`BACKUP_REPO_PATH`), не накапливая историю бинарников.

Обе функции — в самом `backup.py` (не отдельный пакет `backup/` — так и назывался бы модуль `backup.py`, конфликт имён при импорте).

## Ключевые решения

| Решение | Почему |
|---|---|
| SQLite вместо JSON-файлов | Растущее число пользователей и связи между сущностями (история/pantry/профиль) для новых фич; один процесс на одном VPS — не нужен сервер БД. Подробности и альтернативы — `docs/db-migration.md` |
| Structured output от LLM | Обновление памяти и ответ в одном запросе, без цепочек |
| OpenRouter вместо Anthropic API | Pro-подписка Claude не даёт доступ к API |
| `BaseLLMClient` абстракция | Смена провайдера одним классом в `agent/chef.py` |
| `data/` отдельно от кода | Память не смешивается с кодом, простое расположение для бэкапа |
| Мультипользовательский режим с одобрением админом | `ADMIN_USER_ID` из `.env` — единственный, кто approved сразу; остальные после `/start` попадают в `pending` и ждут одобрения через инлайн-кнопки в чате с админом (`memory/users.py`, `bot/handlers.py:handle_approval_callback`) |

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
- Для S3-совместимых хранилищ не-AWS (`S3_ENDPOINT_URL` задан) в `backup.py:_backup_s3()` дополнительно отключены дефолтные контрольные суммы запроса/ответа boto3 (`request_checksum_calculation`/`response_checksum_validation` = `when_required`) — иначе `PutObject` падает с `XAmzContentSHA256Mismatch`, это расширение сторонние провайдеры не поддерживают.

## Онбординг

Запускается когда `profile["onboarding_done"] == false` (профиль из SQLite, `memory/store.py:load_profile`). Шесть вопросов подряд (включая вопрос про технику/посуду), ответы пишутся в profile. Шаг хранится в `profile["onboarding_step"]`: это индекс+1 вопроса, который уже задан и ждёт ответа (`ONBOARDING_QUESTIONS[onboarding_step - 1]`).

`run_onboarding(user_id, user_message)` при `onboarding_step > 0` трактует `user_message` как ответ на текущий вопрос — поэтому его нельзя дёргать с пустой строкой посреди анкеты (затрёт текущий шаг). Для повторного показа текущего вопроса без сайд-эффектов есть `current_onboarding_question(user_id)` (read-only) — им пользуется `/start`, когда анкета не завершена.

После онбординга все сообщения идут через `run_agent()`.

## Команды бота

Все команды, кроме `/pending` и `/broadcast`, доступны только `approved`-пользователям — гейт `_require_approved()` в `bot/handlers.py`, тот же, что у обычных сообщений (new → заявка в pending, pending → молчим, rejected → однократное уведомление).

| Команда | Кому | Что делает | LLM? |
|---|---|---|---|
| `/start` | все | регистрация нового / повтор текущего вопроса анкеты, если онбординг не завершён / сброс контекста диалога (`context_messages`) + приветствие, если завершён | по ситуации |
| `/cook` | approved | шорткат: шлёт агенту фиксированный промпт «предложи рецепт из pantry», дальше как обычное сообщение (LLM, memory_update) | да |
| `/random` | approved | шорткат: промпт «случайное блюдо-сюрприз с учётом вкусов/ограничений» | да |
| `/pantry` | approved | рендер запасов (`pantry_items`) по группам have/low/out | нет |
| `/profile` | approved | рендер профиля (`profiles`/`profile_tags`: вкусы, ограничения, техника) | нет |
| `/reset` | approved | инлайн-меню сброса памяти | нет |
| `/pending` | `ADMIN_USER_ID` | список заявок `pending` с кнопками ✅/❌ | нет |
| `/broadcast <текст>` | `ADMIN_USER_ID` | рассылка всем `approved`-пользователям | нет |

`/cook` и `/random` — не отдельная ветка логики, а просто заготовленный `user_text`, дальше идёт тот же путь, что и у любого сообщения (`_run_agent_reply()` в `bot/handlers.py`). `/pantry` и `/profile` намеренно детерминированные — читают SQLite и рендерят напрямую, без похода к LLM.

### `/reset` и подтверждение опасных действий

`/reset` показывает 3 кнопки (`callback_data="reset:chat|onboarding|all"`):
- `reset:chat` — забыть переписку (таблица `context_messages`), выполняется сразу, не опасно
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
| `BACKUP_BACKEND` | `s3` (по умолчанию) или `git` — куда `backup.py` отправляет снапшот БД |
| `S3_BUCKET`, `S3_PREFIX` | нужны при `BACKUP_BACKEND=s3`; AWS-креды — стандартные `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_DEFAULT_REGION`, их подхватывает `boto3` |
| `S3_ENDPOINT_URL` | нужен для S3-совместимых хранилищ не-AWS — без него `boto3` идёт на настоящий AWS. Пустой = обычный AWS S3 |
| `BACKUP_REPO_PATH` | нужен при `BACKUP_BACKEND=git` — путь к локальному клону приватного репо |
