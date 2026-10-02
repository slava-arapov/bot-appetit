import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
ADMIN_USER_ID = int(os.environ["ADMIN_USER_ID"])

BACKUP_BACKEND = os.environ.get("BACKUP_BACKEND", "s3")  # "s3" | "git"
BACKUP_REPO_PATH = os.environ.get("BACKUP_REPO_PATH", "")
S3_BUCKET = os.environ.get("S3_BUCKET", "")
S3_PREFIX = os.environ.get("S3_PREFIX", "bot-appetit")
S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL", "")  # для S3-совместимых хранилищ (не AWS)
BACKUP_RETENTION_DAYS = 14

LLM_PROVIDER = "openrouter"
LLM_MODELS = [
#     "meta-llama/llama-3.3-70b-instruct:free"
#     "openai/gpt-oss-120b:free"
#     "minimax/minimax-m2.7",
#     "deepseek/deepseek-v3.2",
    "google/gemma-4-26b-a4b-it",
    "minimax/minimax-m2.5",
    "anthropic/claude-haiku-4.5"
]

CONTEXT_WINDOW = 20

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DATA_DIR, "bot.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "memory", "schema.sql")
SNAPSHOT_DIR = os.path.join(DATA_DIR, "snapshots")

EXPIRY_WARNING_DAYS = 2

# Частая техника и посуда: кнопки в онбординге и чек-лист в Mini App (отдаётся через GET /api/profile).
# Значения — в нижнем регистре, как и сохранённые теги `equipment`.
# Порядок важен: в callback_data кнопок онбординга лежит индекс пункта, и уже отправленные
# клавиатуры живут в чатах. Новые пункты добавляй только в конец, не переставляй и не вставляй в середину.
EQUIPMENT_OPTIONS = [
    "духовка",
    "плита",
    "микроволновка",
    "мультиварка",
    "аэрогриль",
    "блендер",
    "миксер",
    "кухонный комбайн",
    "мясорубка",
    "хлебопечь",
    "пароварка",
    "гриль",
]

API_HOST = os.environ.get("API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("API_PORT", "8080"))
INITDATA_MAX_AGE = int(os.environ.get("INITDATA_MAX_AGE", "86400"))  # секунды
