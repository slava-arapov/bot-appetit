# CLAUDE.md — Bot Appetit

## Стек

- Python 3.14, async
- `python-telegram-bot` v20+ (PTB) — async Application, не Updater
- `openrouter` Python-пакет — нативный async-клиент для OpenRouter
- `telegramify-markdown` — конвертирует произвольный markdown в валидный MarkdownV2 для Telegram
- SQLite (`aiosqlite`) — вся память бота, один файл `data/bot.db`
- Mini App: FastAPI (`webapp_api/`, внутри процесса бота) + Vue 3/TypeScript/Vite (`webapp/`)
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
| `profiles` + `profile_tags` | вкусы/ограничения/техника (`profile_tags`, kind = likes/dislikes/restrictions/equipment; значения хранятся в **нижнем регистре**, см. `memory/store.py:normalize_tag`), `servings`, `cooking_time`, онбординг-статус, текущий контекст |
| `history` | блюда с оценками и датами |
| `context_messages` | последние 20 сообщений диалога для LLM |
| `pantry_items` | запасы продуктов: `name`, `status` (have/low/to_buy), `added_date`, опционально `expiry_date` и `quantity` (свободная строка, например "2 пачки") |
| `users` | реестр доступа (status/username/requested_at/approved_at/rejected_at), см. `memory/users.py` — раньше был отдельным `data/users.json` |
| `stats` | счётчики вызовов команд (key/value), см. `memory/stats.py` |

`data/` (вместе с `bot.db`) — в `.gitignore`. Бэкапится через `backup.py`: ежедневный консистентный снапшот (`VACUUM INTO`) → gzip → S3 или git-репо, см. раздел «Бэкап памяти» ниже.

Почему SQLite, а не JSON-файлы или полноценный сервер БД (Postgres) — см. Decision Log в `docs/db-migration.md`. Переход с JSON выполнен разовым скриптом `migrate_to_sqlite.py` (запускается вручную, ничего не удаляет — легаси `data/<user_id>/*.json` стирается вручную после проверки).

Запасы (`pantry_items`) и техника (`equipment`) обновляются так же, как остальная память — через `memory_update` от LLM, без отдельных команд бота. Список покупок — это позиции `pantry_items` со статусом `to_buy` (отдельной таблицы нет). В `memory_update.pantry` `out` значит «закончилось — убрать из запасов» и в БД не хранится; бот в том же ответе спрашивает, добавить ли продукт в покупки, и при согласии следующим сообщением шлёт `to_buy`. «Купил» → `have`. Названия сопоставляются без учёта регистра (`casefold()` в Python: `lower()` в SQLite не понимает кириллицу). При предложении рецепта `to_buy` считается отсутствующим продуктом, `notify_expiring` такие позиции пропускает. Старые строки со статусом `out` мигрируют в `to_buy` в `schema.sql` при старте.

Теги профиля (`profile_tags`) приводятся к нижнему регистру везде, где пишутся: `add_tag`, `save_profile` (онбординг; дубли схлопываются) и `apply_memory_update`. При старте `memory/db.py:_lowercase_tags` идемпотентно переводит в нижний регистр уже сохранённые теги и сливает получившиеся дубли («Духовка» и «духовка» → один тег с меньшим `id`). Делается в Python: `lower()` в SQLite не понимает кириллицу. Названия продуктов в `pantry_items` не нормализуются, они сохраняют регистр, но сопоставляются без его учёта.

Ежедневно в 09:00 `bot/jobs.py:notify_expiring` проходит по всем `approved`-пользователям (`memory/users.py:list_approved_user_ids()`) и для каждого проверяет его запасы (`memory/store.py:check_expiring_soon`) на продукты с `expiry_date` в пределах `EXPIRY_WARNING_DAYS` (см. `config.py`) — детерминированно, без вызова LLM. Регистрируется через `app.job_queue.run_daily(...)` в `main.py` (нужен extra `python-telegram-bot[job-queue]`).

### Mini App: API и dev-окружение

Дизайн — `docs/telegram-mini-app.md` (что делает приложение) и `docs/telegram-mini-app-dev-env.md` (каркас и решения). План реализации по срезам — `docs/telegram-mini-app-implementation.md`. Готовы все срезы v1: «Настройки» (`GET/PATCH /api/settings`), «Pantry» (`GET/POST /api/pantry`, `PATCH/DELETE /api/pantry/{id}`), «Профиль» (`GET /api/profile` — теги по группам плюс `equipment_options`, список техники для чек-листа из `config.EQUIPMENT_OPTIONS`; `POST /api/profile/tags`, `DELETE /api/profile/tags/{id}`) и хаб (`GET /api/summary` — счётчики для подписей карточек; при ошибке карточки остаются без подписей). Точечные операции с `id` (`add_pantry_item`/`update_pantry_item`/`delete_pantry_item`, `add_tag`/`remove_tag`) живут в `memory/store.py` и используются и API, и ботом (`apply_pantry_update`, `apply_memory_update`), чтобы правка из Mini App не терялась из-за load→save всего списка. `save_profile` (полная перезапись с пересозданием тегов) остался только для онбординга и сбросов, поэтому `id` тегов нестабильны между сессиями: фронт при 404 тихо перезапрашивает профиль. UI-библиотека фронта — Vant (выборочно: `SwipeCell`, `Popup`, `Skeleton`), остальное написано самим.

- `webapp_api/` — FastAPI в том же event loop, что и бот: `server.py:start_api()/stop_api()` (uvicorn без перехвата сигналов, при ошибке старта — `RuntimeError`) вызываются из `main.py:_post_init/_post_shutdown`. Использует общее соединение `memory/db.py:get_conn()`. Отключить нельзя — API стартует вместе с ботом.
- Авторизация одна и без dev-обходов: `webapp_api/deps.py:current_user` читает `Authorization: tma <initData>`, `auth.py:validate_init_data` проверяет HMAC-подпись и `auth_date` (`INITDATA_MAX_AGE`), затем статус `approved` в `users` (401 — плохой initData, 403 — нет доступа).
- `webapp/`: `src/telegram/` — обёртка над `Telegram.WebApp` (тема → CSS-переменные `--tg-*`, `viewportStableHeight`) и `mock.ts` для браузера (только dev, в prod-бандл не попадает; активируется при пустом `initData`); `src/api/client.ts` — `apiFetch` с заголовком `tma` (204 → `undefined`, `detail` ошибки берётся только если это строка: у 422 FastAPI он массив). Остальное: `src/composables/` — состояние и запросы на раздел (`useSettings`, `usePantry`, `useProfile`, `useSummary`) и общий `useSnackbar`; `src/components/` — UI по разделам (`settings/`, `pantry/`, `profile/`) и общие `SegmentedControl`, `AppSnackbar`, `HubIcon`; `src/utils/` — чистая логика (статусы и срок годности, склонения подписей хаба); `src/styles/base.css` — токены (`--tap-size`, `--status-*`) и маппинг `--van-*` на `--tg-*`.
- Dev: Vite-плагин `webapp/dev/init-data-plugin.ts` отдаёт свежий подписанный `initData` на `/__dev/init-data` (токен и `ADMIN_USER_ID` из `../.env`; только `vite serve`). Прокси `/api` → `127.0.0.1:8080`. Подпись в TS и проверка в Python — независимые реализации алгоритма Telegram, они проверяют друг друга.
- Тесты: `pytest` (корень, `tests/`, нужен `requirements-dev.txt`), `npm test` / `npm run lint` / `npm run build` в `webapp/`.

### Деплой Mini App

Push в `main` → GitHub Actions (`.github/workflows/deploy.yml`): job `test` гоняет `pytest` и `lint`/`test`/`build` фронта, job `deploy` (только после зелёного `test`) заливает `webapp/dist` на VPS и рестартит бота. Статику из `~/webapp-upload` в `/var/www/botappetit` переносит `rsync` в SSH-скрипте деплоя: nginx не заходит в `/home`. nginx и certbot настраиваются вручную один раз, конфиг — `deploy/nginx-botappetit.conf`, шаги — `deploy/DEPLOY.md`. Миграции данных (`migrate_*.py`) в CI не входят, запускаются руками.

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
- Mini App, фронтенд: вне Telegram `telegram-web-app.js` всё равно создаёт `Telegram.WebApp` с пустым `initData`, поэтому mock (`webapp/src/telegram/mock.ts`) включается по пустому `initData`, а не по отсутствию объекта.
- Mini App, доступ: админ становится `approved` лениво, при первом сообщении боту (`ensure_approved`). Пока таблица `users` пуста, `/api/me` отдаёт 403 — сначала напиши тестовому боту.
- Mini App, UI-библиотека: Vant подключён по компонентам через `unplugin-vue-components` (`webapp/vite.config.ts`); в шаблонах пишутся `<van-skeleton>`, `<van-popup>`, `<van-swipe-cell>` без импортов. В Vitest `vant` приходится пропускать через Vite (`test.server.deps.inline`): иначе Node падает на `.css` из `node_modules`.
- Mini App, тема: `applyTheme` кладёт `themeParams` в `--tg-*`, а `applyScheme` — схему клиента (light/dark) в `data-scheme` на `<html>`. Тема Telegram не равна `prefers-color-scheme`, поэтому цвета статусов запасов переключаются по `[data-scheme='dark']`.
- Mini App, формы: обработчик отправки висит на `@click.prevent` кнопки `type="submit"`, а не на `@submit` формы: jsdom не вызывает `submit` у формы, не прикреплённой к документу, а браузеры превращают Enter в поле в клик по этой кнопке.
- Mini App, тесты фронта: `npm test` нужно запускать из `webapp/`. Запуск `vitest` из корня репозитория не подхватывает конфиг (нет jsdom и Vant) и оставляет пустой `node_modules/.vite`.
- Mini App, dev-сервер: Vite привязан к `127.0.0.1` (`webapp/vite.config.ts`); API стартует вместе с ботом без флага, поэтому порт `API_PORT` (8080) на машине должен быть свободен, иначе бот падает при старте с `RuntimeError`.

## Онбординг

Запускается когда `profile["onboarding_done"] == false` (профиль из SQLite, `memory/store.py:load_profile`). Шесть шагов подряд, описаны списком `ONBOARDING_STEPS` в `agent/chef.py` (`Step(field, question, kind)`). Шаг хранится в `profile["onboarding_step"]`: это индекс+1 вопроса, который уже задан и ждёт ответа (`ONBOARDING_STEPS[onboarding_step - 1]`).

Тип шага (`kind`) задаёт формат ответа, он совпадает с форматом в Mini App:
- `text` (likes, dislikes, restrictions) — свободный текст, режется по запятым и переносам строк в теги.
- `choice` (servings, cooking_time) — кнопки; в `profiles` пишется пресет (`"2"`, `"30"`, `"any"`, как в `set_settings`). Текстовый ответ тоже принимается, если его распознают `normalize_servings` / `normalize_cooking_time` («на 2», «1 час»); иначе шаг повторяется с подсказкой «Выбери вариант кнопкой» и `onboarding_step` не двигается.
- `multiselect` (equipment) — кнопки из `config.EQUIPMENT_OPTIONS` + «✏️ Другое» + «Готово». Тот же список отдаёт Mini App (`equipment_options` в `GET /api/profile`), поэтому правится только в `config.py`. Текст на этом шаге считается «своей» техникой.

`run_onboarding(user_id, user_message)` и `current_onboarding_question(user_id)` возвращают `StepView(text, step)` (`step=None` — анкета закончена). Клавиатуру по `step.kind` строит слой бота (`bot/keyboards.py:keyboard_for`), чтобы `agent/` не зависел от `telegram`. `run_onboarding` при `onboarding_step > 0` трактует `user_message` как ответ на текущий вопрос — поэтому его нельзя дёргать с пустой строкой посреди анкеты (затрёт текущий шаг). Для повторного показа текущего вопроса без сайд-эффектов есть `current_onboarding_question(user_id)` (read-only) — им пользуется `/start`, когда анкета не завершена.

Нажатия кнопок обрабатывает `bot/handlers.py:handle_onboarding_callback` (`callback_data`: `onb:servings:<n>`, `onb:time:<пресет>`, `onb:eq:<индекс в EQUIPMENT_OPTIONS>|other|done`) через `agent/chef.py:apply_onboarding_choice(user_id, field, value)`. Она возвращает `None`, если кнопка устарела (шаг уже пройден, анкета закончена или не начата): хендлер отвечает «Этот вопрос уже неактуален» и убирает клавиатуру, в БД ничего не пишется. Это же защищает от двойного тапа.

Промежуточный выбор техники (индексы галочек, свои пункты, id сообщения с клавиатурой) живёт в `context.user_data` (`onb_equipment`, `onb_custom`, `onb_msg`), в БД пишется только итог по «Готово». После рестарта бота выбор теряется: нажатие на кнопку техники в старом сообщении отвечает «Выбор сбросился, отметь технику заново», гасит старую клавиатуру и показывает шаг заново (пустой список в БД не пишется). `/start` и сброс анкеты обнуляют это состояние (`_reset_onboarding_state`) и гасят кнопки предыдущего сообщения с техникой. Порядок `config.EQUIPMENT_OPTIONS` — контракт с уже отправленными клавиатурами (в `callback_data` лежит индекс): новые пункты добавляй только в конец.

Старые значения в `profiles.servings` / `profiles.cooking_time` (свободный текст из прежнего онбординга) приводит к формату Mini App разовый `migrate_normalize_settings.py` (по умолчанию dry-run, `--apply` делает `*.bak-<дата>` перед записью, идемпотентен). Что он не распознал («Как можно меньше»), остаётся как есть, а Mini App показывает такое поле пустым.

После онбординга все сообщения идут через `run_agent()`.

## Команды бота

Все команды, кроме `/pending` и `/broadcast`, доступны только `approved`-пользователям — гейт `_require_approved()` в `bot/handlers.py`, тот же, что у обычных сообщений (new → заявка в pending, pending → молчим, rejected → однократное уведомление).

| Команда | Кому | Что делает | LLM? |
|---|---|---|---|
| `/start` | все | регистрация нового / повтор текущего вопроса анкеты, если онбординг не завершён / сброс контекста диалога (`context_messages`) + приветствие, если завершён | по ситуации |
| `/cook` | approved | шорткат: шлёт агенту фиксированный промпт «предложи рецепт из pantry», дальше как обычное сообщение (LLM, memory_update) | да |
| `/random` | approved | шорткат: промпт «случайное блюдо-сюрприз с учётом вкусов/ограничений» | да |
| `/pending` | `ADMIN_USER_ID` | список заявок `pending` с кнопками ✅/❌ | нет |
| `/broadcast <текст>` | `ADMIN_USER_ID` | рассылка всем `approved`-пользователям | нет |

`/cook` и `/random` — не отдельная ветка логики, а просто заготовленный `user_text`, дальше идёт тот же путь, что и у любого сообщения (`_run_agent_reply()` в `bot/handlers.py`). Запасы, профиль и сброс памяти в боте командами не доступны — только через Mini App (раздел «Сброс», `POST /api/reset/{chat|onboarding|all}`; логика — `memory/store.py`: `reset_context`, `reset_onboarding`, `reset_all`).

### Меню команд в Telegram (`/`-подсказки)

Регистрируется в `main.py:_post_init()` через `bot.set_my_commands()`. Обычным пользователям — `DEFAULT_COMMANDS`. Админу — `ADMIN_COMMANDS` (то же плюс `/pending`, `/broadcast`) через `scope=BotCommandScopeChat(chat_id=ADMIN_USER_ID)`: Telegram показывает разное меню в зависимости от того, в каком чате пользователь открыл `/`. Работает только если Telegram уже знает `chat_id` пользователя (т.е. тот хоть раз писал боту) — для админа это не проблема, он лениво регистрируется как `approved` в `users.json` при первом же обращении (`memory/users.py:ensure_approved()`, вызывается из `_resolve_access()`), а не одобряется вручную, как остальные.

### Роутинг `CallbackQueryHandler`

В `main.py` два колбэк-хендлера различаются по `pattern` — без этого первый зарегистрированный ловил бы вообще все inline-нажатия:
- `handle_approval_callback` — `pattern=r"^(approve|reject):"` (одобрение заявок)
- `handle_onboarding_callback` — `pattern=r"^onb:"` (кнопки анкеты; сама проверяет, что пользователь `approved`)

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
| `API_HOST`, `API_PORT` | где слушает API Mini App (по умолчанию `127.0.0.1:8080`) |
| `WEBAPP_URL` | публичный `https://`-адрес Mini App (например, `https://botappetit.goida.root.sx`). Если задан, `main.py:_post_init` ставит кнопку меню «Кухня», открывающую его. Пусто — кнопку не трогаем. Не-https адрес пропускается с предупреждением в логе |
| `INITDATA_MAX_AGE` | сколько секунд `initData` считается свежим (по умолчанию 86400) |
