import json
import os

from config import DATA_DIR, STATS_PATH


def _load() -> dict:
    if not os.path.exists(STATS_PATH):
        return {}
    with open(STATS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def record_command(name: str):
    stats = _load()
    stats[name] = stats.get(name, 0) + 1
    _save(stats)


def get_stats() -> dict:
    return _load()
