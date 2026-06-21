import json
import os
from datetime import date, timedelta

from config import (
    PROFILE_PATH,
    HISTORY_PATH,
    CONTEXT_PATH,
    PANTRY_PATH,
    CONTEXT_WINDOW,
    DATA_DIR,
    EXPIRY_WARNING_DAYS,
)

DEFAULT_PROFILE = {
    "likes": [],
    "dislikes": [],
    "restrictions": [],
    "equipment": [],
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
    data = _load_json(HISTORY_PATH, [])
    return data if isinstance(data, list) else []


def save_history(data: list):
    _save_json(HISTORY_PATH, data)


def load_context() -> list:
    return _load_json(CONTEXT_PATH, [])


def save_context(data: list):
    _save_json(CONTEXT_PATH, data)


def load_pantry() -> list:
    data = _load_json(PANTRY_PATH, [])
    return data if isinstance(data, list) else []


def save_pantry(data: list):
    _save_json(PANTRY_PATH, data)


def apply_pantry_update(items: list[dict]):
    """Применяет частичные изменения запасов: добавление/обновление по name, удаление при status=out."""
    if not items:
        return

    pantry = load_pantry()
    by_name = {item["name"]: item for item in pantry}

    for change in items:
        name = change.get("name")
        if not name:
            continue

        if change.get("status") == "out":
            by_name.pop(name, None)
            continue

        existing = by_name.get(name)
        if existing is None:
            existing = {"name": name, "added_date": str(date.today())}
            by_name[name] = existing

        existing["status"] = change.get("status", existing.get("status", "have"))
        if change.get("expiry_date"):
            existing["expiry_date"] = change["expiry_date"]
        if change.get("quantity"):
            existing["quantity"] = change["quantity"]

    save_pantry(list(by_name.values()))


def check_expiring_soon() -> list[dict]:
    """Возвращает записи pantry с expiry_date в пределах EXPIRY_WARNING_DAYS, отсортированные по дате."""
    today = date.today()
    cutoff = today + timedelta(days=EXPIRY_WARNING_DAYS)

    soon = []
    for item in load_pantry():
        expiry_str = item.get("expiry_date")
        if not expiry_str:
            continue
        try:
            expiry = date.fromisoformat(expiry_str)
        except ValueError:
            continue
        if expiry <= cutoff:
            soon.append(item)

    soon.sort(key=lambda i: i["expiry_date"])
    return soon


def apply_memory_update(update: dict):
    if not update:
        return

    profile = load_profile()
    history = load_history()

    for field in ("likes", "dislikes", "restrictions", "equipment"):
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

    apply_pantry_update(update.get("pantry", []))

    save_profile(profile)
