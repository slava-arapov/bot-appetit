# Bot Appetit: как устроено

Живой справочник по текущему устройству бота и Mini App. В отличие от дизайн-документов в `docs/` (они фиксируют решение на момент принятия), этот файл обновляется вместе с кодом. Краткая выжимка и правила для работы с кодом — в `CLAUDE.md`, запуск и деплой — в `README.md` и `deploy/DEPLOY.md`.

## Память — SQLite (`data/bot.db`)

Бот многопользовательский: все таблицы содержат `user_id` (Telegram id) и хранят строки всех пользователей вместе — не отдельные файлы на человека, как было раньше. Все функции в `memory/store.py` и `memory/users.py` — `async def`, принимают `user_id` первым параметром, работают через общее соединение `aiosqlite` из `memory/db.py` (открывается при старте бота в `main.py:_post_init`, схема — `memory/schema.sql`, применяется идемпотентно `CREATE TABLE IF NOT EXISTS`).

| Таблица | Что хранит |
|---|---|
| `profiles` + `profile_tags` | вкусы/ограничения/техника (`profile_tags`, kind = likes/dislikes/restrictions/equipment; значения в нижнем регистре), `servings`, `cooking_time`, онбординг-статус, текущий контекст (`current_context_notes`/`_updated`, см. ниже) |
| `history` | блюда с оценками и датами |
| `context_messages` | последние 20 сообщений диалога для LLM |
| `pantry_items` | запасы продуктов: `name`, `status` (have/low/to_buy), `added_date`, опционально `expiry_date` и `quantity` (свободная строка, например "2 пачки") |
| `users` | реестр доступа (status/username/requested_at/approved_at/rejected_at), см. `memory/users.py` — раньше был отдельным `data/users.json` |
| `stats` | счётчики вызовов команд (key/value), см. `memory/stats.py` |

`data/` (вместе с `bot.db`) — в `.gitignore`. Почему SQLite, а не JSON-файлы или Postgres — Decision Log в `docs/db-migration.md`. Переход с JSON выполнен разовым скриптом `migrate_to_sqlite.py` (запускается вручную, ничего не удаляет — легаси `data/<user_id>/*.json` стирается вручную после проверки).

### Текущий контекст

`current_context_notes`/`_updated` — заметка о ситуации пользователя, которую пишет LLM через `memory_update.current_context`: строка заменяет заметку, `null` стирает, `""` или отсутствие ключа — не трогает (`""` стоит в шаблоне ответа и приходит почти всегда). В промпт идёт с датой «(обновлено YYYY-MM-DD)», чтобы модель видела, что заметка устарела. Видна и очищается в «Профиле» Mini App.

### Запасы и список покупок

Запасы (`pantry_items`) и техника (`equipment`) обновляются так же, как остальная память — через `memory_update` от LLM, без отдельных команд бота. Список покупок — это позиции `pantry_items` со статусом `to_buy` (отдельной таблицы нет).

- В `memory_update.pantry` `out` значит «закончилось — убрать из запасов» и в БД не хранится; бот в том же ответе спрашивает, добавить ли продукт в покупки, и при согласии следующим сообщением шлёт `to_buy`. «Купил» → `have`.
- Названия сопоставляются без учёта регистра (`casefold()` в Python: `lower()` в SQLite не понимает кириллицу). Названия продуктов не нормализуются — сохраняют регистр, но сопоставляются без его учёта.
- При предложении рецепта `to_buy` считается отсутствующим продуктом, `notify_expiring` такие позиции пропускает.
- Старые строки со статусом `out` мигрируют в `to_buy` в `schema.sql` при старте.

### Теги профиля

Теги (`profile_tags`) приводятся к нижнему регистру везде, где пишутся: `add_tag`, `save_profile` (онбординг; дубли схлопываются) и `apply_memory_update` (см. `memory/store.py:normalize_tag`). При старте `memory/db.py:_lowercase_tags` идемпотентно переводит в нижний регистр уже сохранённые теги и сливает получившиеся дубли («Духовка» и «духовка» → один тег с меньшим `id`). Делается в Python по той же причине, что и с продуктами.

### Точечные операции и полная перезапись

Точечные операции с `id` (`add_pantry_item`/`update_pantry_item`/`delete_pantry_item`, `add_tag`/`remove_tag`) живут в `memory/store.py` и используются и API, и ботом (`apply_pantry_update`, `apply_memory_update`), чтобы правка из Mini App не терялась из-за load→save всего списка. `save_profile` (полная перезапись с пересозданием тегов) остался только для онбординга и сбросов, поэтому `id` тегов нестабильны между сессиями: фронт при 404 тихо перезапрашивает профиль.

### Уведомления о сроке годности

Ежедневно в 09:00 `bot/jobs.py:notify_expiring` проходит по всем `approved`-пользователям (`memory/users.py:list_approved_user_ids()`) и для каждого проверяет его запасы (`memory/store.py:check_expiring_soon`) на продукты с `expiry_date` в пределах `EXPIRY_WARNING_DAYS` (см. `config.py`) — детерминированно, без вызова LLM. Регистрируется через `app.job_queue.run_daily(...)` в `main.py` (нужен extra `python-telegram-bot[job-queue]`).

## Онбординг

Запускается когда `profile["onboarding_done"] == false` (`memory/store.py:load_profile`). Шесть шагов подряд, описаны списком `ONBOARDING_STEPS` в `agent/chef.py` (`Step(field, question, kind)`). Шаг хранится в `profile["onboarding_step"]`: это индекс+1 вопроса, который уже задан и ждёт ответа (`ONBOARDING_STEPS[onboarding_step - 1]`). Дизайн и причины — `docs/onboarding-unification.md`.

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

Все команды, кроме админских (`/pending`, `/broadcast`, `/stats`), доступны только `approved`-пользователям — гейт `_require_approved()` в `bot/handlers.py`, тот же, что у обычных сообщений (new → заявка в pending, pending → молчим, rejected → однократное уведомление).

| Команда | Кому | Что делает | LLM? |
|---|---|---|---|
| `/start` | все | регистрация нового / повтор текущего вопроса анкеты, если онбординг не завершён / сброс контекста диалога (`context_messages`) + приветствие, если завершён | по ситуации |
| `/cook` | approved | шорткат: шлёт агенту фиксированный промпт «предложи рецепт из pantry», дальше как обычное сообщение (LLM, memory_update) | да |
| `/random` | approved | шорткат: промпт «случайное блюдо-сюрприз с учётом вкусов/ограничений» | да |
| `/pending` | `ADMIN_USER_ID` | список заявок `pending` с кнопками ✅/❌ | нет |
| `/broadcast <текст>` | `ADMIN_USER_ID` | рассылка всем `approved`-пользователям | нет |
| `/stats` | `ADMIN_USER_ID` | число пользователей по статусам и счётчики вызовов команд (`memory/stats.py`) | нет |

`/cook` и `/random` — не отдельная ветка логики, а просто заготовленный `user_text`, дальше идёт тот же путь, что и у любого сообщения (`_run_agent_reply()` в `bot/handlers.py`). Запасы, профиль и сброс памяти в боте командами не доступны — только через Mini App (раздел «Сброс», `POST /api/reset/{chat|onboarding|all}`; логика — `memory/store.py`: `reset_context`, `reset_onboarding`, `reset_all`).

### Доступ и одобрение

`ADMIN_USER_ID` из `.env` — единственный, кто approved сразу; остальные после `/start` попадают в `pending` и ждут одобрения через инлайн-кнопки в чате с админом (`memory/users.py`, `bot/handlers.py:handle_approval_callback`). Админ регистрируется лениво, при первом обращении (`memory/users.py:ensure_approved()`, вызывается из `_resolve_access()`).

### Меню команд в Telegram (`/`-подсказки)

Регистрируется в `main.py:_post_init()` через `bot.set_my_commands()`. Обычным пользователям — `DEFAULT_COMMANDS`. Админу — `ADMIN_COMMANDS` (то же плюс `/pending`, `/broadcast`, `/stats`) через `scope=BotCommandScopeChat(chat_id=ADMIN_USER_ID)`: Telegram показывает разное меню в зависимости от того, в каком чате пользователь открыл `/`. Работает только если Telegram уже знает `chat_id` пользователя (т.е. тот хоть раз писал боту) — для админа это не проблема, он регистрируется при первом же обращении.

Если задан `WEBAPP_URL`, `main.py:_post_init` ставит кнопку меню «Кухня», открывающую Mini App. Не-https адрес пропускается с предупреждением в логе.

### Роутинг `CallbackQueryHandler`

В `main.py` два колбэк-хендлера различаются по `pattern` — без этого первый зарегистрированный ловил бы вообще все inline-нажатия:
- `handle_approval_callback` — `pattern=r"^(approve|reject):"` (одобрение заявок)
- `handle_onboarding_callback` — `pattern=r"^onb:"` (кнопки анкеты; сама проверяет, что пользователь `approved`)

## Mini App

Дизайн — `docs/telegram-mini-app.md` (что делает приложение) и `docs/telegram-mini-app-dev-env.md` (каркас и решения). План реализации по срезам, отступления и известные ограничения — `docs/telegram-mini-app-implementation.md`.

### API (`webapp_api/`)

FastAPI в том же event loop, что и бот: `server.py:start_api()/stop_api()` (uvicorn без перехвата сигналов, при ошибке старта — `RuntimeError`) вызываются из `main.py:_post_init/_post_shutdown`. Использует общее соединение `memory/db.py:get_conn()`. Отключить нельзя — API стартует вместе с ботом. Swagger — на `/docs`.

Авторизация одна и без dev-обходов: `webapp_api/deps.py:current_user` читает `Authorization: tma <initData>`, `auth.py:validate_init_data` проверяет HMAC-подпись и `auth_date` (`INITDATA_MAX_AGE`), затем статус `approved` в `users` (401 — плохой initData, 403 — нет доступа).

| Раздел | Эндпоинты |
|---|---|
| Настройки | `GET/PATCH /api/settings` |
| Pantry | `GET/POST /api/pantry`, `PATCH/DELETE /api/pantry/{id}` |
| Профиль | `GET /api/profile` — теги по группам, `equipment_options` (список техники для чек-листа из `config.EQUIPMENT_OPTIONS`) и `current_context` (`{notes, updated}`); `POST /api/profile/tags`, `DELETE /api/profile/tags/{id}`; `DELETE /api/profile/context` стирает заметку, `PUT /api/profile/context` возвращает её с прежней датой по «Отменить» |
| Хаб | `GET /api/summary` — счётчики для подписей карточек; при ошибке карточки остаются без подписей |
| Сброс | `POST /api/reset/{chat\|onboarding\|all}` — подтверждение опасных действий на фронте; после `onboarding`/`all` анкета сразу переводится на первый вопрос, а пользователь пишет боту `/start` |

### Фронтенд (`webapp/`)

- `src/telegram/` — обёртка над `Telegram.WebApp` (тема → CSS-переменные `--tg-*`, `viewportStableHeight`, BackButton и `useBackClose` для оверлеев, haptic) и `mock.ts` для браузера (только dev, в prod-бандл не попадает; активируется при пустом `initData`).
- `src/api/client.ts` — `apiFetch` с заголовком `tma` (204 → `undefined`, `detail` ошибки берётся только если это строка: у 422 FastAPI он массив).
- `src/composables/` — состояние и запросы на раздел (`useSettings`, `usePantry`, `useProfile`, `useSummary`) и общий `useSnackbar`.
- `src/views/` — экраны (хаб, Pantry, Профиль, Настройки, Сброс); `src/components/` — UI по разделам (`settings/`, `pantry/`, `profile/`) и общие `SegmentedControl`, `AppSnackbar`, `HubIcon`.
- `src/utils/` — чистая логика (статусы и срок годности, склонения подписей хаба); `src/styles/base.css` — токены (`--tap-size`, `--status-*`) и маппинг `--van-*` на `--tg-*`.
- UI-библиотека — Vant (выборочно: `SwipeCell`, `Popup`, `Skeleton`, подключены через `unplugin-vue-components`), остальное написано самим.

### Dev-окружение

Vite-плагин `webapp/dev/init-data-plugin.ts` отдаёт свежий подписанный `initData` на `/__dev/init-data` (токен и `ADMIN_USER_ID` из `../.env`; только `vite serve`). Прокси `/api` → `127.0.0.1:8080`. Подпись в TS и проверка в Python — независимые реализации алгоритма Telegram, они проверяют друг друга.

## Деплой

Push в `main` → GitHub Actions (`.github/workflows/deploy.yml`): job `test` гоняет `pytest` и `lint`/`test`/`build` фронта, job `deploy` (только после зелёного `test`) заливает `webapp/dist` на VPS и рестартит бота. Статику из `~/webapp-upload` в `/var/www/botappetit` переносит `rsync` в SSH-скрипте деплоя: nginx не заходит в `/home`. nginx и certbot настраиваются вручную один раз, конфиг — `deploy/nginx-botappetit.conf`, шаги — `deploy/DEPLOY.md`. CI конфиг nginx не обновляет. `index.html` отдаётся с `no-cache`, `/assets/` — с `immutable`, иначе WebView Telegram после деплоя показывает старую версию. Миграции данных (`migrate_*.py`) в CI не входят, запускаются руками.

## Бэкап памяти

`backup.py` — отдельный процесс (свой systemd-сервис), не часть основного бота. Ежедневно в 03:00: `VACUUM INTO` консистентный снапшот `data/bot.db` → gzip → отправка в backend, выбираемый `BACKUP_BACKEND`:

- `s3` (по умолчанию) — `_backup_s3()`, через `boto3` в `S3_BUCKET`/`S3_PREFIX`, хранит последние `BACKUP_RETENTION_DAYS` (14) снапшотов, старые удаляет.
- `git` (опция) — `_backup_git()`, коммитит и перезаписывает один файл `bot.db.gz` в приватном репо (`BACKUP_REPO_PATH`), не накапливая историю бинарников.

Обе функции — в самом `backup.py` (не отдельный пакет `backup/` — так и назывался бы модуль `backup.py`, конфликт имён при импорте).

Для S3-совместимых хранилищ не-AWS (`S3_ENDPOINT_URL` задан) в `_backup_s3()` дополнительно отключены дефолтные контрольные суммы запроса/ответа boto3 (`request_checksum_calculation`/`response_checksum_validation` = `when_required`) — иначе `PutObject` падает с `XAmzContentSHA256Mismatch`, это расширение сторонние провайдеры не поддерживают.
