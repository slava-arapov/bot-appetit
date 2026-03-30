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
BACKUP_REPO_PATH=       # опционально: путь к локальному клону приватного репо
```

```bash
python main.py
```

## Структура

```
bot-appetit/
├── agent/chef.py        # сборка промпта, парсинг ответа LLM, логика агента
├── bot/handlers.py      # Telegram-хендлеры (PTB v20+ async)
├── llm/
│   ├── base.py          # абстрактный BaseLLMClient
│   └── openrouter.py    # OpenRouterClient (OpenAI-compatible API)
├── memory/store.py      # чтение/запись JSON-памяти
├── config.py            # конфиг из .env
├── main.py              # точка входа
├── backup.py            # автопуш data/ в приватный git-репо (раз в сутки)
└── data/                # память агента (в .gitignore)
    ├── profile.json     # вкусы, предпочтения, онбординг
    ├── history.json     # история блюд с оценками
    └── context.json     # последние 20 сообщений для LLM
```

## Бэкап памяти

Данные в `data/` не хранятся в этом репо. Для автоматического бэкапа:

1. Создай приватный git-репозиторий
2. Склонируй его локально
3. Укажи путь в `BACKUP_REPO_PATH`
4. Запусти `python backup.py` как отдельный процесс (или через systemd-сервис, см. ниже)

Бэкап запускается ежедневно в 03:00.

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
| `bot-appetit-backup` | Фоновый процесс. Каждый день в 03:00 пушит `data/` в приватный git-репо.            |

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

## Модель

По умолчанию: `anthropic/claude-haiku-4-5` через OpenRouter.
Чтобы сменить модель — поменяй `LLM_MODEL` в `config.py`.

## Backlog

- Несколько пользователей
- Ограничение на количество сообщений в сутки
- Мультиязычность
- Отправляет "Печатает..." во время ожидания ответа
- Сезонность продуктов
- Список покупок
- «Что есть дома» — учёт остатков
- Интеграции с рецептурными базами