import json
import os
from datetime import date

from config import DATA_DIR, USERS_REGISTRY_PATH


def _load_registry() -> dict:
    if not os.path.exists(USERS_REGISTRY_PATH):
        return {}
    with open(USERS_REGISTRY_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save_registry(data: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(USERS_REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_user_status(user_id: int) -> str | None:
    entry = _load_registry().get(str(user_id))
    return entry["status"] if entry else None


def register_pending(user_id: int, username: str | None):
    registry = _load_registry()
    registry[str(user_id)] = {
        "status": "pending",
        "username": username or "",
        "requested_at": str(date.today()),
    }
    _save_registry(registry)


def approve_user(user_id: int):
    registry = _load_registry()
    entry = registry.setdefault(str(user_id), {})
    entry["status"] = "approved"
    entry["approved_at"] = str(date.today())
    _save_registry(registry)


def reject_user(user_id: int):
    registry = _load_registry()
    entry = registry.setdefault(str(user_id), {})
    entry["status"] = "rejected"
    entry["rejected_at"] = str(date.today())
    entry["rejection_notified"] = False
    _save_registry(registry)


def mark_rejection_notified(user_id: int):
    registry = _load_registry()
    entry = registry.get(str(user_id))
    if entry:
        entry["rejection_notified"] = True
        _save_registry(registry)


def is_rejection_notified(user_id: int) -> bool:
    entry = _load_registry().get(str(user_id))
    return bool(entry and entry.get("rejection_notified"))


def list_approved_user_ids() -> list[int]:
    registry = _load_registry()
    return [int(uid) for uid, entry in registry.items() if entry.get("status") == "approved"]
