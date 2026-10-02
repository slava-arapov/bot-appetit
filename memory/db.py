import os

import aiosqlite

from config import DB_PATH, SCHEMA_PATH

_conn: aiosqlite.Connection | None = None


async def init_db() -> aiosqlite.Connection:
    global _conn
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    _conn = await aiosqlite.connect(DB_PATH)
    _conn.row_factory = aiosqlite.Row
    await _conn.execute("PRAGMA journal_mode=WAL")
    await _conn.execute("PRAGMA foreign_keys=ON")
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        await _conn.executescript(f.read())
    await _conn.commit()
    await _lowercase_tags(_conn)
    return _conn


async def _lowercase_tags(conn: aiosqlite.Connection):
    """Миграция: теги профиля хранятся в нижнем регистре. Идемпотентна.

    Приводит старые значения к нижнему регистру и сливает получившиеся дубли (остаётся тег с меньшим id).
    Делается в Python, а не в SQL: SQLite lower() не понимает кириллицу.
    """
    cursor = await conn.execute("SELECT id, user_id, kind, value FROM profile_tags ORDER BY id")
    seen: set[tuple[int, str, str]] = set()
    renames: list[tuple[str, int]] = []
    duplicates: list[tuple[int]] = []
    for row in await cursor.fetchall():
        value = row["value"].strip().lower()
        key = (row["user_id"], row["kind"], value)
        if key in seen:
            duplicates.append((row["id"],))
            continue
        seen.add(key)
        if value != row["value"]:
            renames.append((value, row["id"]))

    if not renames and not duplicates:
        return
    await conn.executemany("UPDATE profile_tags SET value = ? WHERE id = ?", renames)
    await conn.executemany("DELETE FROM profile_tags WHERE id = ?", duplicates)
    await conn.commit()


async def close_db():
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None


def get_conn() -> aiosqlite.Connection:
    if _conn is None:
        raise RuntimeError("БД не инициализирована — вызови init_db() при старте приложения")
    return _conn
