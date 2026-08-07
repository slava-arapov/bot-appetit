# Деплой bot-appetit на VPS

## Порядок первичного развёртывания

### 1. Подготовка VPS

```bash
# Python 3.14 пока не в стандартных репозиториях Ubuntu — добавь deadsnakes PPA
sudo apt update && sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update

# Установи Python 3.14 и git
sudo apt install -y python3.14 python3.14-venv git

# Создай пользователя для бота
sudo useradd -m -s /bin/bash botappetit
sudo su - botappetit

# Клонируй репозиторий
git clone https://github.com/slava-arapov/bot-appetit.git ~/bot-appetit
cd ~/bot-appetit

# Виртуальное окружение
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Создай .env (бэкап по умолчанию в S3, см. раздел "2. Бэкап данных" про альтернативу через git)
cat > .env << EOF
TELEGRAM_TOKEN=...
OPENROUTER_API_KEY=...
ADMIN_USER_ID=...

BACKUP_BACKEND=s3
S3_BUCKET=...
S3_PREFIX=bot-appetit
S3_ENDPOINT_URL=        # только для S3-совместимых хранилищ не-AWS; пусто = обычный AWS S3
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=...
EOF

# Создай папку data/ — здесь будет жить data/bot.db (SQLite) и data/snapshots/ (локальные снапшоты перед отправкой в бэкап)
mkdir -p data
```

### 2. Бэкап данных

Память бота — один файл SQLite (`data/bot.db`). `backup.py` ежедневно делает консистентный снапшот (`VACUUM INTO`), сжимает gzip'ом и отправляет в один из двух backend'ов, выбираемый переменной `BACKUP_BACKEND`.

**Backend `s3` (по умолчанию)** — нужен S3-совместимый бакет и ключи доступа (`S3_BUCKET`, `S3_PREFIX`, стандартные `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_DEFAULT_REGION` в `.env`, использует `boto3`, который сам их подхватывает). Хранит последние `BACKUP_RETENTION_DAYS` (14) снапшотов, старые удаляет автоматически.

Для не-AWS хранилища (S3-совместимые) обязательно укажи `S3_ENDPOINT_URL` — без него `boto3` пытается стучаться в настоящий AWS.

**Backend `git` (опция)** — коммитит один и тот же файл `bot.db.gz` в приватный репозиторий на каждый бэкап (не накапливая историю бинарников списком файлов). Нужен `BACKUP_REPO_PATH` в `.env` и доступ VPS к приватному репо по SSH (deploy key), HTTPS-clone без авторизации не сработает:

```bash
# Сгенерируй ключ от имени botappetit
ssh-keygen -t ed25519 -f ~/.ssh/backup_key -N ""
cat ~/.ssh/backup_key.pub   # скопируй вывод
```

Добавь публичный ключ в GitHub → репо `bot-appetit-data` → **Settings → Deploy keys** (с правом записи).

Добавь в `~/.ssh/config`:
```
Host github.com
    IdentityFile ~/.ssh/backup_key
```

Теперь можно клонировать (по SSH, чтобы использовался deploy key):

```bash
# Клонируй приватный репо для бэкапа данных
git clone git@github.com:slava-arapov/bot-appetit-data.git ~/bot-appetit-data

# Настрой git identity (нужна для коммитов из backup.py)
git config --global user.email "backup-bot@server"
git config --global user.name "Bot Backup"
```

И в `.env` вместо `BACKUP_BACKEND=s3` — `BACKUP_BACKEND=git` и `BACKUP_REPO_PATH=/home/botappetit/bot-appetit-data`.

### 3. Systemd-сервисы

`botappetit` не в sudoers — эти команды нужно выполнять от имени обычного админского пользователя, которым ты подключился по SSH, а не из-под `botappetit`. Сначала выйди из его сессии:

```bash
exit   # вернуться из-под botappetit к админскому пользователю
```

```bash
# Скопируй unit-файлы из репо
sudo cp ~botappetit/bot-appetit/deploy/bot-appetit.service /etc/systemd/system/
sudo cp ~botappetit/bot-appetit/deploy/bot-appetit-backup.service /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable bot-appetit bot-appetit-backup
sudo systemctl start bot-appetit bot-appetit-backup

# Проверь
sudo systemctl status bot-appetit bot-appetit-backup
```

### 4. Права для CI/CD (sudo без пароля)

Тоже от имени админского пользователя:

```bash
sudo visudo -f /etc/sudoers.d/botappetit
```

Добавь строку:
```
botappetit ALL=(ALL) NOPASSWD: /bin/systemctl restart bot-appetit
```

### 5. SSH-ключ для GitHub Actions

Ключ и `authorized_keys` должны принадлежать `botappetit` — вернись в его сессию:

```bash
sudo su - botappetit

# Сгенерируй отдельный ключ для деплоя (от имени botappetit)
ssh-keygen -t ed25519 -f ~/.ssh/deploy_key -N ""

# Добавь публичный ключ в authorized_keys
cat ~/.ssh/deploy_key.pub >> ~/.ssh/authorized_keys

# Выведи приватный ключ — скопируй в GitHub Secret SSH_KEY
cat ~/.ssh/deploy_key
```

### 6. GitHub Secrets

В репозитории → **Settings → Secrets and variables → Actions**:

| Secret     | Значение                           |
|------------|------------------------------------|
| `SSH_HOST` | IP адрес VPS                       |
| `SSH_USER` | `botappetit`                       |
| `SSH_KEY`  | приватный ключ `~/.ssh/deploy_key` |
| `SSH_PORT` | `22` (или другой)                  |

---

## Как работает CI/CD

Каждый `git push` в `main`:

```
push → GitHub Actions → SSH на VPS → git pull + pip install → systemctl restart bot-appetit
```

Деплой занимает ~20 секунд. Данные в `data/` не трогаются.

---

## Перенос локальной папки data/ на VPS

На новом деплое ничего переносить не нужно — `data/bot.db` создаётся автоматически при первом старте бота (применяется `memory/schema.sql`).

Этот раздел — для одноразового переноса **уже существующей** легаси-папки `data/<user_id>/*.json` (со старой, JSON-based версии бота) на VPS, чтобы прогнать по ней `migrate_to_sqlite.py`.

Прямого SSH-доступа к `botappetit` нет (только deploy key для CI/CD), поэтому копируем через админский аккаунт и переносим с правильным владельцем:

```bash
# 1. С локальной машины скопируй data/ в home админа на VPS
scp -r ./data YOUR_USER@YOUR_VPS_IP:~/

# 2. Зайди на VPS под админом
ssh YOUR_USER@YOUR_VPS_IP

# 3. Перенеси папку в директорию бота и передай владение botappetit
sudo mv ~/data /home/botappetit/bot-appetit/data
sudo chown -R botappetit:botappetit /home/botappetit/bot-appetit/data

# 4. Прогони миграцию в SQLite (бот должен быть остановлен)
sudo systemctl stop bot-appetit
sudo su - botappetit
cd ~/bot-appetit && source .venv/bin/activate && python migrate_to_sqlite.py
# сверь числа в выводе с содержимым старых JSON, затем вручную удали
# data/<user_id>/, data/users.json, data/stats.json — скрипт их не трогает
exit

# 5. Перезапусти бота, чтобы он подхватил bot.db
sudo systemctl start bot-appetit
```

---

## Полезные команды

```bash
# Статус сервисов
sudo systemctl status bot-appetit
sudo systemctl status bot-appetit-backup

# Живые логи
sudo journalctl -u bot-appetit -f
sudo journalctl -u bot-appetit-backup -f

# Ручной рестарт
sudo systemctl restart bot-appetit

# Принудительный бэкап прямо сейчас
sudo su - botappetit
cd ~/bot-appetit && source .venv/bin/activate && python backup.py --now
```
