import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
ADMIN_USER_ID = int(os.environ["ADMIN_USER_ID"])
BACKUP_REPO_PATH = os.environ.get("BACKUP_REPO_PATH", "")

LLM_PROVIDER = "openrouter"
LLM_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "openai/gpt-oss-120b:free",
    "anthropic/claude-haiku-4-5"
]

CONTEXT_WINDOW = 20

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PROFILE_PATH = os.path.join(DATA_DIR, "profile.json")
HISTORY_PATH = os.path.join(DATA_DIR, "history.json")
CONTEXT_PATH = os.path.join(DATA_DIR, "context.json")
