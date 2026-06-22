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

# Создай .env
cat > .env << EOF
TELEGRAM_TOKEN=...
OPENROUTER_API_KEY=...
ADMIN_USER_ID=...
BACKUP_REPO_PATH=/home/botappetit/bot-appetit-data
EOF

# Создай папку data/
mkdir -p data
```

### 2. Бэкап данных

Репозиторий `bot-appetit-data` приватный — сначала нужен доступ по SSH (deploy key), HTTPS-clone без авторизации не сработает.

**Доступ VPS к приватному репо — SSH Deploy Key:**

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

Прямого SSH-доступа к `botappetit` нет (только deploy key для CI/CD), поэтому копируем через админский аккаунт и переносим с правильным владельцем:

```bash
# 1. С локальной машины скопируй data/ в home админа на VPS
scp -r ./data YOUR_USER@YOUR_VPS_IP:~/

# 2. Зайди на VPS под админом
ssh YOUR_USER@YOUR_VPS_IP

# 3. Перенеси папку в директорию бота и передай владение botappetit
sudo mv ~/data /home/botappetit/bot-appetit/data
sudo chown -R botappetit:botappetit /home/botappetit/bot-appetit/data

# 4. Перезапусти бота, чтобы он подхватил данные
sudo systemctl restart bot-appetit
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
