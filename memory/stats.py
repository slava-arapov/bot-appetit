from memory.db import get_conn


async def record_command(name: str):
    conn = get_conn()
    await conn.execute(
        """
        INSERT INTO stats (key, value) VALUES (?, 1)
        ON CONFLICT(key) DO UPDATE SET value = value + 1
        """,
        (name,),
    )
    await conn.commit()


async def get_stats() -> dict:
    conn = get_conn()
    cursor = await conn.execute("SELECT key, value FROM stats")
    return {r["key"]: r["value"] for r in await cursor.fetchall()}
