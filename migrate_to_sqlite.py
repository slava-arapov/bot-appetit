"""Разовая миграция данных из data/<user_id>/*.json (+ users.json, stats.json) в data/bot.db.

Запускать вручную один раз, после остановки бота:

    python migrate_to_sqlite.py

Ничего не удаляет из data/ — только читает JSON и пишет в SQLite. В конце печатает
отчёт сверки количества строк. Если что-то не сошлось — исходные файлы остаются
нетронутыми, разбирайся и запускай заново (скрипт идемпотентен: таблицы создаются
через CREATE TABLE IF NOT EXISTS, но повторный запуск задвоит строки, поэтому перед
повторным запуском удали свежесозданный data/bot.db).
"""

import json
import os
import sqlite3
import sys

from config import DATA_DIR, DB_PATH, SCHEMA_PATH

# Старые имена файлов — начиная с этой миграции они больше не нужны конфигу,
# но здесь остаются захардкоженными как разовая привязка к легаси-формату.
PROFILE_FILENAME = "profile.json"
HISTORY_FILENAME = "history.json"
CONTEXT_FILENAME = "context.json"
PANTRY_FILENAME = "pantry.json"
USERS_REGISTRY_PATH = os.path.join(DATA_DIR, "users.json")
STATS_PATH = os.path.join(DATA_DIR, "stats.json")

_TAG_KINDS = ("likes", "dislikes", "restrictions", "equipment")


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _user_dirs():
    if not os.path.isdir(DATA_DIR):
        return []
    return sorted(
        name for name in os.listdir(DATA_DIR)
        if name.isdigit() and os.path.isdir(os.path.join(DATA_DIR, name))
    )


def main():
    if os.path.exists(DB_PATH):
        print(f"{DB_PATH} уже существует — удали его перед повторным запуском миграции.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())

    report = {"users": 0, "profiles": 0, "profile_tags": 0, "history": 0,
              "pantry_items": 0, "context_messages": 0, "stats": 0, "skipped_users": []}

    # users.json — источник истины по статусу доступа
    registry = _load_json(USERS_REGISTRY_PATH, {})
    known_user_ids = set()
    for uid_str, entry in registry.items():
        uid = int(uid_str)
        known_user_ids.add(uid)
        conn.execute(
            """
            INSERT INTO users (user_id, username, status, requested_at, approved_at,
                                rejected_at, rejection_notified)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uid,
                entry.get("username", ""),
                entry.get("status", "approved"),
                entry.get("requested_at"),
                entry.get("approved_at"),
                entry.get("rejected_at"),
                int(bool(entry.get("rejection_notified"))),
            ),
        )
        report["users"] += 1

    # data/<user_id>/*.json
    for uid_str in _user_dirs():
        uid = int(uid_str)
        if uid not in known_user_ids:
            print(f"⚠ data/{uid}/ есть, но user_id отсутствует в users.json — пропускаю")
            report["skipped_users"].append(uid)
            continue

        user_dir = os.path.join(DATA_DIR, uid_str)

        profile = _load_json(os.path.join(user_dir, PROFILE_FILENAME), {})
        if profile:
            context = profile.get("current_context") or {}
            conn.execute(
                """
                INSERT INTO profiles (user_id, onboarding_done, onboarding_step, servings,
                                       cooking_time, current_context_notes, current_context_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uid,
                    int(bool(profile.get("onboarding_done"))),
                    profile.get("onboarding_step", 0),
                    profile.get("servings"),
                    profile.get("cooking_time"),
                    context.get("notes"),
                    context.get("updated"),
                ),
            )
            report["profiles"] += 1

            for kind in _TAG_KINDS:
                for value in profile.get(kind, []):
                    conn.execute(
                        "INSERT INTO profile_tags (user_id, kind, value) VALUES (?, ?, ?)",
                        (uid, kind, value),
                    )
                    report["profile_tags"] += 1

        for entry in _load_json(os.path.join(user_dir, HISTORY_FILENAME), []):
            conn.execute(
                "INSERT INTO history (user_id, dish, rating, date) VALUES (?, ?, ?, ?)",
                (uid, entry.get("dish"), entry.get("rating"), entry.get("date")),
            )
            report["history"] += 1

        for item in _load_json(os.path.join(user_dir, PANTRY_FILENAME), []):
            conn.execute(
                "INSERT INTO pantry_items (user_id, name, status, added_date, expiry_date, quantity) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    uid, item.get("name"), item.get("status", "have"),
                    item.get("added_date"), item.get("expiry_date"), item.get("quantity"),
                ),
            )
            report["pantry_items"] += 1

        for msg in _load_json(os.path.join(user_dir, CONTEXT_FILENAME), []):
            conn.execute(
                "INSERT INTO context_messages (user_id, role, content) VALUES (?, ?, ?)",
                (uid, msg.get("role"), msg.get("content")),
            )
            report["context_messages"] += 1

    # stats.json
    stats = _load_json(STATS_PATH, {})
    for key, value in stats.items():
        conn.execute("INSERT INTO stats (key, value) VALUES (?, ?)", (key, value))
        report["stats"] += 1

    conn.commit()
    conn.close()

    print("\nМиграция завершена. Строк вставлено:")
    for key in ("users", "profiles", "profile_tags", "history", "pantry_items", "context_messages", "stats"):
        print(f"  {key}: {report[key]}")
    if report["skipped_users"]:
        print(f"\n⚠ Пропущено пользователей без записи в users.json: {report['skipped_users']}")
    print(
        f"\nБаза данных создана: {DB_PATH}\n"
        "Сверь числа с исходными JSON вручную, запусти бота на БД и убедись, что всё "
        "работает. Только после этого можно вручную удалить data/<user_id>/, "
        "data/users.json и data/stats.json."
    )


if __name__ == "__main__":
    main()
