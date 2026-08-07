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
    return _conn


async def close_db():
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None


def get_conn() -> aiosqlite.Connection:
    if _conn is None:
        raise RuntimeError("БД не инициализирована — вызови init_db() при старте приложения")
    return _conn
