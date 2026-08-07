# Переход памяти бота с JSON-файлов на SQLite

Дизайн-документ. Зафиксирован по итогам обсуждения 2026-08-07. Реализация — отдельным шагом.

## Понимание задачи

- Сейчас память бота — JSON-файлы в `data/<user_id>/*.json` (`profile.json`, `history.json`, `context.json`, `pantry.json`) плюс `data/users.json` (реестр доступа) и `data/stats.json`.
- Растёт число пользователей, и новые фичи (избранные рецепты, категории в `pantry`, списки покупок) требуют связей между сущностями — плоские JSON-файлы на пользователя для этого неудобны.
- Бот работает на одном VPS, один процесс (PTB async), рассчитан на десятки-сотни пользователей — не multi-instance, не публичный высоконагруженный сервис.
- Бэкап сейчас — `backup.py` коммитит и пушит весь `data/` в приватный гит-репо по расписанию (`schedule`). Гит-репо не приспособлен для бинарного файла БД.
- После миграции `data/`-файлы полностью убираются, ручной шаг — вручную, после проверки, что бот стабильно работает на БД.
- Новые фичи (избранные рецепты, списки покупок, категории pantry) **в этот дизайн не входят** — только перенос существующей структуры данных. Схема под них — отдельный дизайн позже.

## Допущения

1. Доступ к БД нужен только из одного процесса бота на одном VPS — не из нескольких процессов/машин одновременно.
2. Объём данных остаётся умеренным (сотни пользователей × десятки записей истории/pantry) — не десятки ГБ.
3. RPO бэкапов — около суток (как сейчас), даунтайм в несколько минут на миграцию допустим.

## Decision Log

| Решение | Альтернативы | Почему |
|---|---|---|
| SQLite, один файл `data/bot.db`, без ORM (raw SQL + `aiosqlite`) | PostgreSQL в Docker; SQLAlchemy/ORM; JSON с ручными id-связями | Один процесс на одном VPS, умеренный масштаб — SQL закрывает потребность в связях без сервера БД. ORM даёт мало пользы на 6 таблицах без сложных JOIN'ов и добавляет async-engine/session сложность; защита от будущей миграции на другую СУБД уже обеспечена слоем абстракции в `memory/store.py`/`memory/users.py`, а не выбором ORM |
| Схема — только перенос текущих сущностей, без полей под будущие фичи (рецепты, shopping list, категории pantry) | Сразу заложить таблицы под будущие фичи | YAGNI — фичи не спроектированы, поля будут гаданием |
| `profile_tags` как отдельная таблица (kind/value) вместо 4 JSON-массивов в одной строке | Хранить `likes/dislikes/restrictions/equipment` как JSON-колонки в `profiles` | Позволяет добавлять/удалять один тег без перезаписи всего списка |
| Даты — `TEXT` в формате ISO-8601 (`YYYY-MM-DD`) | `INTEGER` unix timestamp; `REAL` julianday | ISO-8601 строки сортируются лексикографически так же, как хронологически; встроенные функции SQLite (`date()`, `strftime()`, сравнения) работают с ними напрямую. Код уже везде генерирует даты через `date.today()`/`.isoformat()` |
| `context_messages` без отдельной колонки `position` | Хранить явный порядковый номер сообщения | `INTEGER PRIMARY KEY` в SQLite — это rowid, монотонно растёт при вставке; `ORDER BY id` уже даёт порядок вставки |
| Миграция данных — разовый ручной скрипт, `data/` удаляется вручную после проверки | Автоудаление `data/` в конце скрипта | Удаление необратимо; нужно время убедиться, что бот стабильно работает на БД, прежде чем стирать источник |
| Бэкап: `VACUUM INTO` снапшот + pluggable backend (`BACKUP_BACKEND=s3\|git`, дефолт S3) | Прямое копирование файла БД; только S3; только git | Прямое копирование небезопасно в WAL-режиме (файлы `-wal`/`-shm`); явный запрос — оставить git как настраиваемую опцию, не единственный путь |

## Финальный дизайн

### Схема БД

```sql
users(
  user_id INTEGER PRIMARY KEY,  -- Telegram user id, передаётся явно при INSERT, не автогенерируется
  username TEXT,
  status TEXT,              -- pending/approved/rejected
  requested_at TEXT, approved_at TEXT, rejected_at TEXT,
  rejection_notified INTEGER DEFAULT 0
)

profiles(
  user_id INTEGER PRIMARY KEY REFERENCES users(user_id),
  onboarding_done INTEGER DEFAULT 0,
  onboarding_step INTEGER DEFAULT 0,
  servings TEXT,       -- "на сколько человек обычно готовит" (анкета)
  cooking_time TEXT,   -- "сколько времени готов тратить" (анкета)
  current_context_notes TEXT,
  current_context_updated TEXT
)

profile_tags(id INTEGER PRIMARY KEY, user_id INTEGER, kind TEXT, value TEXT)
  -- kind: likes / dislikes / restrictions / equipment

history(id INTEGER PRIMARY KEY, user_id INTEGER, dish TEXT, rating TEXT, date TEXT)

pantry_items(
  id INTEGER PRIMARY KEY, user_id INTEGER, name TEXT, status TEXT,
  added_date TEXT, expiry_date TEXT, quantity TEXT
)

context_messages(
  id INTEGER PRIMARY KEY, user_id INTEGER,
  role TEXT, content TEXT
)

stats(key TEXT PRIMARY KEY, value INTEGER)
```

Примеры запросов на дальнейшее использование:

```sql
-- продукты с истекающим сроком (замена check_expiring_soon)
SELECT * FROM pantry_items
WHERE user_id = ? AND expiry_date IS NOT NULL
  AND expiry_date <= date('now', '+' || ? || ' days')
ORDER BY expiry_date;

-- последние 20 сообщений контекста в хронологическом порядке
SELECT role, content FROM (
  SELECT id, role, content FROM context_messages
  WHERE user_id = ? ORDER BY id DESC LIMIT 20
) ORDER BY id ASC;
```

### Слой доступа к данным

- Новый модуль `memory/db.py`: одно соединение `aiosqlite.connect("data/bot.db")`, открывается при старте (`main.py`) и живёт в контексте приложения. При открытии — `PRAGMA journal_mode=WAL` и `PRAGMA foreign_keys=ON`.
- Схема — файл `memory/schema.sql` с `CREATE TABLE IF NOT EXISTS ...`, применяется один раз при старте. Отдельный migration-framework не нужен на этом масштабе; если схема начнёт часто меняться, тогда добавляется `schema_version` + нумерованные `.sql`-файлы.
- `memory/store.py` и `memory/users.py` сохраняют те же публичные функции с теми же именами и сигнатурами, но становятся `async def` и делают SQL вместо чтения файлов.
- Все вызовы этих функций в `bot/handlers.py`, `agent/chef.py`, `bot/jobs.py` становятся `await`-нутыми — механическая, но затрагивающая все три модуля правка.
- ORM не используется — raw SQL, без SQLAlchemy.

### Миграция данных

Разовый скрипт `migrate_to_sqlite.py` в корне репозитория:

1. Создаёт `data/bot.db`, накатывает `memory/schema.sql`.
2. Читает `data/users.json` → таблица `users` (источник истины по `status`).
3. Обходит существующие `data/<user_id>/` (не у всех `pending`-пользователей есть папка) → `profiles`, `profile_tags`, `history`, `context_messages`, `pantry_items`.
4. Читает `data/stats.json` → `stats`.
5. Печатает отчёт сверки (число строк по каждой таблице против исходных JSON). Расхождение — стоп, ничего не удаляется.
6. `data/` **не удаляется скриптом** — ручной шаг после того, как отчёт сошёлся и бот подтверждённо стабильно проработал на БД.

### Бэкапы

- Снапшот БД — не прямое копирование файла (небезопасно в WAL-режиме из-за `-wal`/`-shm`), а `VACUUM INTO 'snapshots/bot-<date>.db'`: консистентный компактный снапшот, безопасный при работающем боте. Сжимается gzip перед отправкой.
- `backup.py` остаётся точкой входа и планировщиком (`schedule`, ежедневно, уведомление админу при ошибке — как сейчас), меняется только что бэкапится и куда отправляется.
- Backend выбирается через `BACKUP_BACKEND` (`.env`, `s3` | `git`, дефолт `s3`). Реализованы как функции `_backup_s3()`/`_backup_git()` прямо в `backup.py` (не отдельный пакет `backup/` — так и назывался бы как модуль `backup.py`, конфликт имён; для двух функций отдельные файлы были бы лишней структурой):
  - `_backup_s3()` — `boto3`, кладёт снапшот в `S3_BUCKET`/`S3_PREFIX`, credentials — стандартные `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`.
  - `_backup_git()` — переиспользует прежнюю `_git()`-логику, но коммитит и перезаписывает один бинарный снапшот (`bot.db.gz`), не накапливая историю бинарников в репозитории.
- Ротация: хранятся последние 14 дневных снапшотов, старые удаляются (в S3 — lifecycle-правило бакета или руками в коде; в git-backend — просто перезапись файла).

## Вне рамок этого дизайна

- Схема и функциональность для избранных рецептов, категорий pantry, списков покупок — отдельный дизайн после того, как эти фичи будут проработаны.
- Переход на PostgreSQL, ORM/SQLAlchemy, multi-instance деплой — не планируются, но слой абстракции в `memory/store.py`/`memory/users.py` не создаёт препятствий для этого в будущем.
