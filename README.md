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
4. Запусти `python backup.py` как отдельный процесс

Бэкап запускается ежедневно в 03:00.

## Модель

По умолчанию: `anthropic/claude-haiku-4-5` через OpenRouter.
Чтобы сменить модель — поменяй `LLM_MODEL` в `config.py`.

## Backlog

- Сезонность продуктов
- Список покупок
- «Что есть дома» — учёт остатков
- Интеграции с рецептурными базами