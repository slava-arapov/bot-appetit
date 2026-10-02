"""Разовая нормализация profiles.servings / profiles.cooking_time под формат Mini App.

Онбординг раньше писал в эти поля свободный текст («1 час», «на 1», «Не важно»),
а Mini App ждёт число 1–8 и пресет времени 15/30/60/any. Запускать вручную:

    python migrate_normalize_settings.py                # dry-run: только отчёт
    python migrate_normalize_settings.py --apply        # записать (перед этим делает *.bak-<дата>)
    python migrate_normalize_settings.py --db путь.db   # по умолчанию data/bot.db

Пишет только однозначные значения (то, что распознают normalize_servings / normalize_cooking_time).
Нераспознанное («Как можно меньше») не трогает, а перечисляет в отчёте: Mini App покажет такое поле
пустым, пока пользователь не выберет значение сам. Идемпотентен: повторный запуск ничего не меняет.
Лучше запускать при остановленном боте.
"""

import argparse
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime

from config import DB_PATH
from memory.store import normalize_cooking_time, normalize_servings

_FIELDS = {"servings": normalize_servings, "cooking_time": normalize_cooking_time}


@dataclass(frozen=True)
class Change:
    user_id: int
    field: str
    old: str
    new: str


@dataclass(frozen=True)
class Unrecognized:
    user_id: int
    field: str
    value: str


def plan(conn: sqlite3.Connection) -> tuple[list[Change], list[Unrecognized]]:
    changes: list[Change] = []
    unrecognized: list[Unrecognized] = []
    rows = conn.execute("SELECT user_id, servings, cooking_time FROM profiles ORDER BY user_id").fetchall()
    for user_id, servings, cooking_time in rows:
        for field, raw in (("servings", servings), ("cooking_time", cooking_time)):
            if raw is None or not str(raw).strip():
                continue
            value = _FIELDS[field](raw)
            if value is None:
                unrecognized.append(Unrecognized(user_id, field, raw))
            elif str(value) != raw:
                changes.append(Change(user_id, field, raw, str(value)))
    return changes, unrecognized


def _print_report(changes: list[Change], unrecognized: list[Unrecognized]):
    if changes:
        print(f"К изменению ({len(changes)}):")
        for c in changes:
            print(f"  user {c.user_id}: {c.field}: {c.old!r} -> {c.new!r}")
    else:
        print("Нечего менять: все распознаваемые значения уже нормализованы.")
    if unrecognized:
        print(f"\nНе распознано, остаётся как есть ({len(unrecognized)}):")
        for u in unrecognized:
            print(f"  user {u.user_id}: {u.field}: {u.value!r}")


def _backup(conn: sqlite3.Connection, db_path: str) -> str:
    path = f"{db_path}.bak-{datetime.now():%Y%m%d-%H%M%S}"
    target = sqlite3.connect(path)
    try:
        conn.backup(target)  # консистентная копия, в том числе при WAL
    finally:
        target.close()
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=DB_PATH, help="путь к bot.db (по умолчанию data/bot.db)")
    parser.add_argument("--apply", action="store_true", help="записать изменения (по умолчанию dry-run)")
    args = parser.parse_args(argv)

    if not os.path.exists(args.db):
        print(f"{args.db} не найден.")
        return 1

    conn = sqlite3.connect(args.db)
    try:
        changes, unrecognized = plan(conn)
        _print_report(changes, unrecognized)

        if not changes:
            return 0
        if not args.apply:
            print("\nDry-run: ничего не записано. Для записи добавь --apply.")
            return 0

        backup_path = _backup(conn, args.db)
        print(f"\nБэкап: {backup_path}")
        with conn:
            for c in changes:
                conn.execute(f"UPDATE profiles SET {c.field} = ? WHERE user_id = ?", (c.new, c.user_id))
        print(f"Записано изменений: {len(changes)}.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
