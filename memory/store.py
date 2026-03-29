import json
import os
from datetime import date

from config import PROFILE_PATH, HISTORY_PATH, CONTEXT_PATH, CONTEXT_WINDOW, DATA_DIR

DEFAULT_PROFILE = {
    "likes": [],
    "dislikes": [],
    "restrictions": [],
    "onboarding_done": False,
    "onboarding_step": 0,
    "current_context": {"notes": "", "updated": ""},
}


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_json(path: str, default):
    _ensure_data_dir()
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: str, data):
    _ensure_data_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_profile() -> dict:
    profile = _load_json(PROFILE_PATH, {})
    # Заполнить отсутствующие поля дефолтами
    for key, value in DEFAULT_PROFILE.items():
        if key not in profile:
            profile[key] = value
    return profile


def save_profile(data: dict):
    _save_json(PROFILE_PATH, data)


def load_history() -> list:
    return _load_json(HISTORY_PATH, [])


def save_history(data: list):
    _save_json(HISTORY_PATH, data)


def load_context() -> list:
    return _load_json(CONTEXT_PATH, [])


def save_context(data: list):
    _save_json(CONTEXT_PATH, data)


def apply_memory_update(update: dict):
    if not update:
        return

    profile = load_profile()
    history = load_history()

    for field in ("likes", "dislikes", "restrictions"):
        if not isinstance(profile[field], list):
            profile[field] = []
        new_items = update.get(field, [])
        for item in new_items:
            # Стрипаем префикс "добавить: " если есть
            clean = item.removeprefix("добавить: ").strip()
            if clean and clean not in profile[field]:
                profile[field].append(clean)

    if "current_context" in update and update["current_context"]:
        profile["current_context"] = {
            "notes": update["current_context"],
            "updated": str(date.today()),
        }

    if "history" in update and update["history"]:
        entry = update["history"]
        if isinstance(entry, dict) and "dish" in entry:
            entry.setdefault("date", str(date.today()))
            history.append(entry)
            save_history(history)

    save_profile(profile)
