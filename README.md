# Bot Appetit

Персональный Telegram-бот шеф-повар с памятью о вкусах пользователя. Работает через OpenRouter.

## Быстрый старт

```bash
pip install -r requirements.txt
```

Заполни `.env`:

```
TELEGRAM_TOKEN=...
OPENROUTER_API_KEY=...
ADMIN_USER_ID=...       # твой Telegram ID (узнать: @userinfobot)

# Бэкап (см. раздел "Бэкап памяти" ниже)
BACKUP_BACKEND=s3       # s3 (по умолчанию) или git
S3_BUCKET=...
S3_PREFIX=bot-appetit
S3_ENDPOINT_URL=        # только для S3-совместимых хранилищ не-AWS; пусто = обычный AWS S3
# AWS-креды подхватывает boto3 сам: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_DEFAULT_REGION
BACKUP_REPO_PATH=       # только если BACKUP_BACKEND=git — путь к локальному клону приватного репо
```

```bash
python main.py
```

## Команды

| Команда    | Описание                                               |
|------------|--------------------------------------------------------|
| `/start`   | Первый запуск; если анкета не закончена — повторяет текущий вопрос; если всё готово — сбрасывает переписку и здоровается заново |
| `/cook`    | Предложить рецепт из того, что есть дома               |
| `/random`  | Случайное блюдо-сюрприз с учётом вкусов и ограничений  |
| `/pantry`  | Показать текущие запасы (есть / заканчивается / нет)   |
| `/profile` | Показать вкусы, ограничения и технику                  |
| `/reset`   | Сбросить память бота (переписку, анкету или всё сразу) |

В остальном с ботом можно просто общаться в свободной форме: что есть дома, что хочется приготовить, что купил или доел — он сам обновит память и предложит рецепт.

**Для админа** (`ADMIN_USER_ID`) дополнительно доступны:

| Команда              | Описание                                               |
|----------------------|--------------------------------------------------------|
| `/pending`           | Список заявок на доступ, с кнопками одобрить/отклонить |
| `/broadcast <текст>` | Разослать сообщение всем одобренным пользователям      |

## Структура

```
bot-appetit/
├── agent/chef.py        # сборка промпта, парсинг ответа LLM, логика агента
├── bot/
│   ├── handlers.py      # Telegram-хендлеры (PTB v20+ async), "печатает...", одобрение заявок
│   └── jobs.py          # фоновые задачи (уведомления об истекающих продуктах)
├── llm/
│   ├── base.py          # абстрактный BaseLLMClient
│   └── openrouter.py    # OpenRouterClient (openrouter пакет, нативный async)
├── memory/
│   ├── db.py            # aiosqlite-соединение, применение schema.sql при старте
│   ├── schema.sql        # схема SQLite (users, profiles, profile_tags, history, pantry_items, context_messages, stats)
│   ├── store.py         # чтение/запись памяти пользователей (async, SQLite)
│   ├── users.py         # реестр доступа (async, SQLite; pending/approved/rejected)
│   └── stats.py         # счётчики вызовов команд (async, SQLite)
├── deploy/              # systemd unit-файлы
├── docs/db-migration.md # дизайн-документ перехода с JSON на SQLite (rationale, decision log)
├── config.py            # конфиг из .env
├── main.py              # точка входа
├── migrate_to_sqlite.py # разовый скрипт миграции легаси JSON → SQLite
├── backup.py            # ежедневный снапшот data/bot.db → S3 или git-репо
└── data/                # память агента (в .gitignore)
    ├── bot.db            # SQLite — вся память бота
    └── snapshots/        # локальные снапшоты перед отправкой в бэкап
```

## Бэкап памяти

Вся память бота — один файл SQLite (`data/bot.db`). `backup.py` ежедневно в 03:00 делает консистентный снапшот (`VACUUM INTO`), сжимает gzip'ом и отправляет в один из двух backend'ов (`BACKUP_BACKEND` в `.env`):

- **`s3`** (по умолчанию) — нужен S3-бакет и AWS-креды, см. `.env`-блок выше. Хранит последние 14 снапшотов, старые удаляет сам.
- **`git`** — коммитит и перезаписывает один файл `bot.db.gz` в приватном репозитории (`BACKUP_REPO_PATH`), без накопления истории бинарников.

Запусти `python backup.py` как отдельный процесс (или через systemd-сервис, см. ниже) — либо `python backup.py --now` для разового бэкапа прямо сейчас.

## Деплой на VPS

### Systemd-сервисы

В папке `deploy/` лежат готовые unit-файлы для systemd.

**Установка:**

```bash
sudo cp deploy/bot-appetit.service /etc/systemd/system/
sudo cp deploy/bot-appetit-backup.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable bot-appetit bot-appetit-backup
sudo systemctl start bot-appetit bot-appetit-backup
```

| Сервис               | Что делает                                                                          |
|----------------------|-------------------------------------------------------------------------------------|
| `bot-appetit`        | Основной бот. Перезапускается автоматически при краше и при каждом деплое через CI. |
| `bot-appetit-backup` | Фоновый процесс. Каждый день в 03:00 делает снапшот `data/bot.db` и отправляет в S3 или git-репо (см. «Бэкап памяти»). |

**Полезные команды:**

```bash
sudo systemctl status bot-appetit          # статус бота
sudo journalctl -u bot-appetit -f          # живые логи
sudo systemctl restart bot-appetit         # ручной рестарт
```

### CI/CD (GitHub Actions)

Каждый `git push` в `main` автоматически деплоит на VPS:
`git pull → pip install → systemctl restart bot-appetit`

Для работы нужно добавить в **Settings → Secrets** репозитория:

| Secret     | Значение               |
|------------|------------------------|
| `SSH_HOST` | IP адрес VPS           |
| `SSH_USER` | пользователь на VPS    |
| `SSH_KEY`  | приватный SSH-ключ     |
| `SSH_PORT` | порт SSH (обычно `22`) |

> Пользователю на VPS нужно право запускать `sudo systemctl restart bot-appetit` без пароля.
> Добавь в `/etc/sudoers.d/botappetit`:
> ```
> botappetit ALL=(ALL) NOPASSWD: /bin/systemctl restart bot-appetit
> ```

## Модели

По умолчанию используется список моделей `LLM_MODELS` в `config.py` — бот пробует их по очереди по throughput. Имя выбранной модели отображается в конце каждого ответа как Telegram-спойлер.

Чтобы сменить модели — поменяй `LLM_MODELS` в `config.py`.

## Backlog

- Ограничение на количество сообщений в сутки
- Мультиязычность
- Сезонность продуктов
- Список покупок
- Интеграции с рецептурными базами
