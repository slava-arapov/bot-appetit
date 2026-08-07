from datetime import date, timedelta

from config import EXPIRY_WARNING_DAYS
from memory.db import get_conn

_TAG_KINDS = ("likes", "dislikes", "restrictions", "equipment")

DEFAULT_PROFILE = {
    "likes": [],
    "dislikes": [],
    "restrictions": [],
    "equipment": [],
    "onboarding_done": False,
    "onboarding_step": 0,
    "current_context": {"notes": "", "updated": ""},
}


async def load_profile(user_id: int) -> dict:
    conn = get_conn()
    row = await (await conn.execute(
        "SELECT * FROM profiles WHERE user_id = ?", (user_id,)
    )).fetchone()

    profile = dict(DEFAULT_PROFILE)
    profile["current_context"] = dict(DEFAULT_PROFILE["current_context"])
    if row:
        profile["onboarding_done"] = bool(row["onboarding_done"])
        profile["onboarding_step"] = row["onboarding_step"]
        profile["current_context"] = {
            "notes": row["current_context_notes"] or "",
            "updated": row["current_context_updated"] or "",
        }
        if row["servings"]:
            profile["servings"] = row["servings"]
        if row["cooking_time"]:
            profile["cooking_time"] = row["cooking_time"]

    for kind in _TAG_KINDS:
        cursor = await conn.execute(
            "SELECT value FROM profile_tags WHERE user_id = ? AND kind = ? ORDER BY id",
            (user_id, kind),
        )
        profile[kind] = [r["value"] for r in await cursor.fetchall()]

    return profile


async def save_profile(user_id: int, data: dict):
    conn = get_conn()
    context = data.get("current_context") or {}
    await conn.execute(
        """
        INSERT INTO profiles (user_id, onboarding_done, onboarding_step, servings, cooking_time,
                               current_context_notes, current_context_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
          onboarding_done = excluded.onboarding_done,
          onboarding_step = excluded.onboarding_step,
          servings = excluded.servings,
          cooking_time = excluded.cooking_time,
          current_context_notes = excluded.current_context_notes,
          current_context_updated = excluded.current_context_updated
        """,
        (
            user_id,
            int(bool(data.get("onboarding_done"))),
            data.get("onboarding_step", 0),
            data.get("servings"),
            data.get("cooking_time"),
            context.get("notes"),
            context.get("updated"),
        ),
    )

    for kind in _TAG_KINDS:
        await conn.execute("DELETE FROM profile_tags WHERE user_id = ? AND kind = ?", (user_id, kind))
        values = data.get(kind, [])
        if values:
            await conn.executemany(
                "INSERT INTO profile_tags (user_id, kind, value) VALUES (?, ?, ?)",
                [(user_id, kind, v) for v in values],
            )

    await conn.commit()


async def load_history(user_id: int) -> list:
    conn = get_conn()
    cursor = await conn.execute(
        "SELECT dish, rating, date FROM history WHERE user_id = ? ORDER BY id", (user_id,)
    )
    return [dict(r) for r in await cursor.fetchall()]


async def save_history(user_id: int, data: list):
    conn = get_conn()
    await conn.execute("DELETE FROM history WHERE user_id = ?", (user_id,))
    if data:
        await conn.executemany(
            "INSERT INTO history (user_id, dish, rating, date) VALUES (?, ?, ?, ?)",
            [(user_id, e.get("dish"), e.get("rating"), e.get("date")) for e in data],
        )
    await conn.commit()


async def load_context(user_id: int) -> list:
    conn = get_conn()
    cursor = await conn.execute(
        "SELECT role, content FROM context_messages WHERE user_id = ? ORDER BY id", (user_id,)
    )
    return [dict(r) for r in await cursor.fetchall()]


async def save_context(user_id: int, data: list):
    conn = get_conn()
    await conn.execute("DELETE FROM context_messages WHERE user_id = ?", (user_id,))
    if data:
        await conn.executemany(
            "INSERT INTO context_messages (user_id, role, content) VALUES (?, ?, ?)",
            [(user_id, m.get("role"), m.get("content")) for m in data],
        )
    await conn.commit()


async def load_pantry(user_id: int) -> list:
    conn = get_conn()
    cursor = await conn.execute(
        "SELECT name, status, added_date, expiry_date, quantity FROM pantry_items WHERE user_id = ? ORDER BY id",
        (user_id,),
    )
    return [dict(r) for r in await cursor.fetchall()]


async def save_pantry(user_id: int, data: list):
    conn = get_conn()
    await conn.execute("DELETE FROM pantry_items WHERE user_id = ?", (user_id,))
    if data:
        await conn.executemany(
            "INSERT INTO pantry_items (user_id, name, status, added_date, expiry_date, quantity) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (user_id, i["name"], i.get("status", "have"), i.get("added_date"), i.get("expiry_date"), i.get("quantity"))
                for i in data
            ],
        )
    await conn.commit()


async def apply_pantry_update(user_id: int, items: list[dict]):
    """Применяет частичные изменения запасов: добавление/обновление по name, удаление при status=out."""
    if not items:
        return

    pantry = await load_pantry(user_id)
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

    await save_pantry(user_id, list(by_name.values()))


async def check_expiring_soon(user_id: int) -> list[dict]:
    """Возвращает записи pantry с expiry_date в пределах EXPIRY_WARNING_DAYS, отсортированные по дате."""
    today = date.today()
    cutoff = today + timedelta(days=EXPIRY_WARNING_DAYS)

    soon = []
    for item in await load_pantry(user_id):
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


async def reset_context(user_id: int):
    await save_context(user_id, [])


async def reset_onboarding(user_id: int):
    profile = await load_profile(user_id)
    profile["onboarding_done"] = False
    profile["onboarding_step"] = 0
    await save_profile(user_id, profile)


async def reset_all(user_id: int):
    await save_profile(user_id, {
        "likes": [],
        "dislikes": [],
        "restrictions": [],
        "equipment": [],
        "onboarding_done": False,
        "onboarding_step": 0,
        "current_context": {"notes": "", "updated": ""},
    })
    await save_history(user_id, [])
    await save_context(user_id, [])
    await save_pantry(user_id, [])


async def apply_memory_update(user_id: int, update: dict):
    if not update:
        return

    profile = await load_profile(user_id)
    history = await load_history(user_id)

    for field in _TAG_KINDS:
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
        entries = update["history"]
        if isinstance(entries, dict):
            entries = [entries]
        if isinstance(entries, list):
            changed = False
            for entry in entries:
                if isinstance(entry, dict) and "dish" in entry:
                    entry.setdefault("date", str(date.today()))
                    history.append(entry)
                    changed = True
            if changed:
                await save_history(user_id, history)

    await apply_pantry_update(user_id, update.get("pantry", []))

    await save_profile(user_id, profile)
