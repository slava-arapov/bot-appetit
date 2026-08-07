from datetime import date

from memory.db import get_conn


async def get_user_status(user_id: int) -> str | None:
    conn = get_conn()
    row = await (await conn.execute(
        "SELECT status FROM users WHERE user_id = ?", (user_id,)
    )).fetchone()
    return row["status"] if row else None


async def register_pending(user_id: int, username: str | None):
    conn = get_conn()
    await conn.execute(
        """
        INSERT INTO users (user_id, username, status, requested_at)
        VALUES (?, ?, 'pending', ?)
        ON CONFLICT(user_id) DO UPDATE SET
          username = excluded.username,
          status = 'pending',
          requested_at = excluded.requested_at
        """,
        (user_id, username or "", str(date.today())),
    )
    await conn.commit()


async def ensure_approved(user_id: int, username: str | None = None):
    conn = get_conn()
    row = await (await conn.execute(
        "SELECT status, username, approved_at FROM users WHERE user_id = ?", (user_id,)
    )).fetchone()
    if row and row["status"] == "approved":
        return

    await conn.execute(
        """
        INSERT INTO users (user_id, username, status, approved_at)
        VALUES (?, ?, 'approved', ?)
        ON CONFLICT(user_id) DO UPDATE SET
          status = 'approved',
          username = COALESCE(NULLIF(users.username, ''), excluded.username),
          approved_at = COALESCE(users.approved_at, excluded.approved_at)
        """,
        (user_id, username or "", str(date.today())),
    )
    await conn.commit()


async def approve_user(user_id: int):
    conn = get_conn()
    await conn.execute(
        """
        INSERT INTO users (user_id, status, approved_at) VALUES (?, 'approved', ?)
        ON CONFLICT(user_id) DO UPDATE SET status = 'approved', approved_at = excluded.approved_at
        """,
        (user_id, str(date.today())),
    )
    await conn.commit()


async def reject_user(user_id: int):
    conn = get_conn()
    await conn.execute(
        """
        INSERT INTO users (user_id, status, rejected_at, rejection_notified) VALUES (?, 'rejected', ?, 0)
        ON CONFLICT(user_id) DO UPDATE SET
          status = 'rejected', rejected_at = excluded.rejected_at, rejection_notified = 0
        """,
        (user_id, str(date.today())),
    )
    await conn.commit()


async def mark_rejection_notified(user_id: int):
    conn = get_conn()
    await conn.execute(
        "UPDATE users SET rejection_notified = 1 WHERE user_id = ?", (user_id,)
    )
    await conn.commit()


async def is_rejection_notified(user_id: int) -> bool:
    conn = get_conn()
    row = await (await conn.execute(
        "SELECT rejection_notified FROM users WHERE user_id = ?", (user_id,)
    )).fetchone()
    return bool(row and row["rejection_notified"])


async def list_approved_user_ids() -> list[int]:
    conn = get_conn()
    cursor = await conn.execute("SELECT user_id FROM users WHERE status = 'approved'")
    return [r["user_id"] for r in await cursor.fetchall()]


async def list_pending_users() -> list[dict]:
    conn = get_conn()
    cursor = await conn.execute(
        "SELECT user_id, username, requested_at FROM users WHERE status = 'pending'"
    )
    return [dict(r) for r in await cursor.fetchall()]


async def count_users_by_status() -> dict:
    conn = get_conn()
    cursor = await conn.execute(
        "SELECT status, COUNT(*) AS n FROM users WHERE status IN ('approved', 'pending', 'rejected') GROUP BY status"
    )
    counts = {"approved": 0, "pending": 0, "rejected": 0}
    for row in await cursor.fetchall():
        counts[row["status"]] = row["n"]
    return counts
