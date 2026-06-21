import json
import os
from datetime import date, timedelta

from config import (
    PROFILE_FILENAME,
    HISTORY_FILENAME,
    CONTEXT_FILENAME,
    PANTRY_FILENAME,
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


def _user_dir(user_id: int) -> str:
    return os.path.join(DATA_DIR, str(user_id))


def _user_path(user_id: int, filename: str) -> str:
    return os.path.join(_user_dir(user_id), filename)


def _ensure_user_dir(user_id: int):
    os.makedirs(_user_dir(user_id), exist_ok=True)


def _load_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_json(user_id: int, path: str, data):
    _ensure_user_dir(user_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_profile(user_id: int) -> dict:
    profile = _load_json(_user_path(user_id, PROFILE_FILENAME), {})
    # Заполнить отсутствующие поля дефолтами
    for key, value in DEFAULT_PROFILE.items():
        if key not in profile:
            profile[key] = value
    return profile


def save_profile(user_id: int, data: dict):
    _save_json(user_id, _user_path(user_id, PROFILE_FILENAME), data)


def load_history(user_id: int) -> list:
    data = _load_json(_user_path(user_id, HISTORY_FILENAME), [])
    return data if isinstance(data, list) else []


def save_history(user_id: int, data: list):
    _save_json(user_id, _user_path(user_id, HISTORY_FILENAME), data)


def load_context(user_id: int) -> list:
    return _load_json(_user_path(user_id, CONTEXT_FILENAME), [])


def save_context(user_id: int, data: list):
    _save_json(user_id, _user_path(user_id, CONTEXT_FILENAME), data)


def load_pantry(user_id: int) -> list:
    data = _load_json(_user_path(user_id, PANTRY_FILENAME), [])
    return data if isinstance(data, list) else []


def save_pantry(user_id: int, data: list):
    _save_json(user_id, _user_path(user_id, PANTRY_FILENAME), data)


def apply_pantry_update(user_id: int, items: list[dict]):
    """Применяет частичные изменения запасов: добавление/обновление по name, удаление при status=out."""
    if not items:
        return

    pantry = load_pantry(user_id)
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

    save_pantry(user_id, list(by_name.values()))


def check_expiring_soon(user_id: int) -> list[dict]:
    """Возвращает записи pantry с expiry_date в пределах EXPIRY_WARNING_DAYS, отсортированные по дате."""
    today = date.today()
    cutoff = today + timedelta(days=EXPIRY_WARNING_DAYS)

    soon = []
    for item in load_pantry(user_id):
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


def apply_memory_update(user_id: int, update: dict):
    if not update:
        return

    profile = load_profile(user_id)
    history = load_history(user_id)

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
            save_history(user_id, history)

    apply_pantry_update(user_id, update.get("pantry", []))

    save_profile(user_id, profile)
