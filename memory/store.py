import re
from datetime import date, timedelta

from config import EXPIRY_WARNING_DAYS
from memory.db import get_conn

_TAG_KINDS = ("likes", "dislikes", "restrictions", "equipment")

def normalize_tag(value: str) -> str:
    """Теги профиля хранятся без пробелов по краям и в нижнем регистре («Духовка» и «духовка» — один тег)."""
    # lower() в Python, а не в SQL: SQLite lower() не понимает кириллицу
    return value.strip().lower()


SERVINGS_RANGE = (1, 8)
COOKING_TIME_PRESETS = ("15", "30", "60", "any")

# to_buy — позиция списка покупок. "out" в БД не хранится: от LLM он означает «закончилось, убрать из запасов».
PANTRY_STATUSES = ("have", "low", "to_buy")
_PANTRY_EDITABLE = ("name", "status", "quantity", "expiry_date")


class PantryNameTaken(ValueError):
    """В запасах уже есть позиция с таким названием (без учёта регистра)."""

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
        # теги хранятся в нижнем регистре; dict.fromkeys убирает дубли, сохраняя порядок
        values = list(dict.fromkeys(filter(None, map(normalize_tag, data.get(kind, [])))))
        if values:
            await conn.executemany(
                "INSERT INTO profile_tags (user_id, kind, value) VALUES (?, ?, ?)",
                [(user_id, kind, v) for v in values],
            )

    await conn.commit()


def normalize_servings(raw: str | None) -> int | None:
    """Первое число из строки в диапазоне SERVINGS_RANGE, иначе None (старые значения — свободный текст)."""
    match = re.search(r"\d+", raw or "")
    if not match:
        return None
    value = int(match.group())
    low, high = SERVINGS_RANGE
    return value if low <= value <= high else None


_ONE_HOUR_RE = re.compile(r"(?:(?:до|не\s+более|не\s+больше|около|максимум)\s+)?(?:1\s*)?(?:час|часа|ч)\.?")


_NON_MINUTE_UNIT_RE = re.compile(r"\d+\s*(?:ч\b|час|сут|дн|нед|мес)")


def normalize_cooking_time(raw: str | None) -> str | None:
    """Приводит значение к пресету из COOKING_TIME_PRESETS, иначе None. Ближайший пресет не подбирает."""
    text = (raw or "").strip().lower()
    if text in COOKING_TIME_PRESETS:
        return text
    # «не важно» и «неважно» пишут по-разному, да и фраза бывает длиннее («не важно, любое.»)
    if re.search(r"не\s*важно", text):
        return "any"
    # «час», «1 ч», «до часа», «не более 1 часа» — ровно один час; «2 часа» и «полтора часа» не округляем
    if _ONE_HOUR_RE.fullmatch(text):
        return "60"
    # число с единицей не «минуты» («30 часов», «2 часа 30 минут») нельзя читать как минуты
    if _NON_MINUTE_UNIT_RE.search(text):
        return None
    match = re.search(r"\d+", text)
    if match and match.group() in COOKING_TIME_PRESETS:
        return match.group()
    return None


def describe_servings(raw: str | None) -> str | None:
    """Человекочитаемая строка для промпта и /profile; нераспознанный текст возвращается как есть."""
    count = normalize_servings(raw)
    if count is None:
        return raw or None
    if count % 10 == 1 and count % 100 != 11:
        word = "порция"
    elif 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        word = "порции"
    else:
        word = "порций"
    return f"{count} {word}"


def describe_cooking_time(raw: str | None) -> str | None:
    preset = normalize_cooking_time(raw)
    if preset is None:
        return raw or None
    return "время не важно" if preset == "any" else f"до {preset} минут"


async def get_settings(user_id: int) -> dict:
    conn = get_conn()
    row = await (await conn.execute(
        "SELECT servings, cooking_time FROM profiles WHERE user_id = ?", (user_id,)
    )).fetchone()
    return {
        "servings": normalize_servings(row["servings"]) if row else None,
        "cooking_time": normalize_cooking_time(row["cooking_time"]) if row else None,
    }


async def set_settings(user_id: int, *, servings: int | None = None, cooking_time: str | None = None):
    """Обновляет только переданные поля, не трогая остальной профиль."""
    conn = get_conn()
    await conn.execute("INSERT OR IGNORE INTO profiles (user_id) VALUES (?)", (user_id,))
    if servings is not None:
        await conn.execute(
            "UPDATE profiles SET servings = ? WHERE user_id = ?", (str(servings), user_id)
        )
    if cooking_time is not None:
        await conn.execute(
            "UPDATE profiles SET cooking_time = ? WHERE user_id = ?", (cooking_time, user_id)
        )
    await conn.commit()


async def list_tags(user_id: int) -> dict[str, list[dict]]:
    """Теги по всем kind вместе с id: {kind: [{id, value}]}."""
    conn = get_conn()
    tags: dict[str, list[dict]] = {kind: [] for kind in _TAG_KINDS}
    cursor = await conn.execute(
        "SELECT id, kind, value FROM profile_tags WHERE user_id = ? ORDER BY id", (user_id,)
    )
    for row in await cursor.fetchall():
        if row["kind"] in tags:
            tags[row["kind"]].append({"id": row["id"], "value": row["value"]})
    return tags


async def add_tag(user_id: int, kind: str, value: str) -> dict:
    """Добавляет тег в нижнем регистре; если такой уже есть в этом kind, возвращает существующий."""
    if kind not in _TAG_KINDS:
        raise ValueError(f"Неизвестный вид тега: {kind}")
    value = normalize_tag(value)

    for tag in (await list_tags(user_id))[kind]:
        if tag["value"] == value:
            return {"id": tag["id"], "kind": kind, "value": tag["value"]}

    conn = get_conn()
    cursor = await conn.execute(
        "INSERT INTO profile_tags (user_id, kind, value) VALUES (?, ?, ?)", (user_id, kind, value)
    )
    await conn.commit()
    return {"id": cursor.lastrowid, "kind": kind, "value": value}


async def remove_tag(user_id: int, tag_id: int) -> bool:
    conn = get_conn()
    cursor = await conn.execute(
        "DELETE FROM profile_tags WHERE user_id = ? AND id = ?", (user_id, tag_id)
    )
    await conn.commit()
    return cursor.rowcount > 0


async def set_current_context(user_id: int, notes: str, updated: str):
    conn = get_conn()
    await conn.execute("INSERT OR IGNORE INTO profiles (user_id) VALUES (?)", (user_id,))
    await conn.execute(
        "UPDATE profiles SET current_context_notes = ?, current_context_updated = ? WHERE user_id = ?",
        (notes, updated, user_id),
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


async def list_pantry(user_id: int) -> list[dict]:
    conn = get_conn()
    cursor = await conn.execute(
        "SELECT id, name, status, added_date, expiry_date, quantity FROM pantry_items "
        "WHERE user_id = ? ORDER BY id",
        (user_id,),
    )
    return [dict(r) for r in await cursor.fetchall()]


async def load_pantry(user_id: int) -> list:
    return await list_pantry(user_id)


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


async def _get_pantry_item(user_id: int, item_id: int) -> dict | None:
    cursor = await get_conn().execute(
        "SELECT id, name, status, added_date, expiry_date, quantity FROM pantry_items "
        "WHERE user_id = ? AND id = ?",
        (user_id, item_id),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def _find_pantry_by_name(user_id: int, name: str) -> dict | None:
    # casefold в Python: SQLite lower() не понимает кириллицу
    key = name.strip().casefold()
    for item in await list_pantry(user_id):
        if item["name"].casefold() == key:
            return item
    return None


async def add_pantry_item(
    user_id: int,
    name: str,
    *,
    status: str = "have",
    quantity: str | None = None,
    expiry_date: str | None = None,
) -> dict:
    """Добавляет позицию; если такое название уже есть, обновляет существующую, а не плодит дубль."""
    name = name.strip()
    existing = await _find_pantry_by_name(user_id, name)
    if existing:
        fields = {"status": status}
        if quantity:
            fields["quantity"] = quantity
        if expiry_date:
            fields["expiry_date"] = expiry_date
        return await update_pantry_item(user_id, existing["id"], **fields)

    conn = get_conn()
    cursor = await conn.execute(
        "INSERT INTO pantry_items (user_id, name, status, added_date, expiry_date, quantity) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, name, status, str(date.today()), expiry_date, quantity),
    )
    await conn.commit()
    return await _get_pantry_item(user_id, cursor.lastrowid)


async def update_pantry_item(user_id: int, item_id: int, **fields) -> dict | None:
    """Меняет только переданные поля (None очищает quantity/expiry_date). None, если позиции нет у пользователя."""
    unknown = set(fields) - set(_PANTRY_EDITABLE)
    if unknown:
        raise ValueError(f"Неизвестные поля: {sorted(unknown)}")

    item = await _get_pantry_item(user_id, item_id)
    if item is None:
        return None
    if not fields:
        return item

    if "name" in fields:
        fields["name"] = fields["name"].strip()
        same_name = await _find_pantry_by_name(user_id, fields["name"])
        if same_name and same_name["id"] != item_id:
            raise PantryNameTaken(fields["name"])

    conn = get_conn()
    # имена колонок берутся только из белого списка _PANTRY_EDITABLE
    assignments = ", ".join(f"{column} = ?" for column in fields)
    await conn.execute(
        f"UPDATE pantry_items SET {assignments} WHERE user_id = ? AND id = ?",
        (*fields.values(), user_id, item_id),
    )
    await conn.commit()
    return await _get_pantry_item(user_id, item_id)


async def delete_pantry_item(user_id: int, item_id: int) -> bool:
    conn = get_conn()
    cursor = await conn.execute(
        "DELETE FROM pantry_items WHERE user_id = ? AND id = ?", (user_id, item_id)
    )
    await conn.commit()
    return cursor.rowcount > 0


async def apply_pantry_update(user_id: int, items: list[dict]):
    """Применяет частичные изменения запасов от LLM.

    out — убрать позицию из запасов; to_buy — добавить в список покупок; have/low — обновить статус.
    Совпадение по названию без учёта регистра.
    """
    for change in items or []:
        name = (change.get("name") or "").strip()
        if not name:
            continue

        status = change.get("status")
        existing = await _find_pantry_by_name(user_id, name)

        if status == "out":
            if existing:
                await delete_pantry_item(user_id, existing["id"])
            continue

        fields = {}
        if status in PANTRY_STATUSES:
            fields["status"] = status
        if change.get("expiry_date"):
            fields["expiry_date"] = change["expiry_date"]
        if change.get("quantity"):
            fields["quantity"] = change["quantity"]

        if existing is None:
            await add_pantry_item(user_id, name, **fields)
        elif fields:
            await update_pantry_item(user_id, existing["id"], **fields)


async def check_expiring_soon(user_id: int) -> list[dict]:
    """Возвращает записи pantry с expiry_date в пределах EXPIRY_WARNING_DAYS, отсортированные по дате."""
    today = date.today()
    cutoff = today + timedelta(days=EXPIRY_WARNING_DAYS)

    soon = []
    for item in await load_pantry(user_id):
        if item.get("status") == "to_buy":
            continue
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
    """Применяет memory_update от LLM точечными операциями: id тегов при этом не меняются."""
    if not update:
        return

    for kind in _TAG_KINDS:
        for item in update.get(kind, []):
            # Стрипаем префикс "добавить: " если есть
            clean = item.removeprefix("добавить: ").strip()
            if clean:
                await add_tag(user_id, kind, clean)

    if update.get("current_context"):
        await set_current_context(user_id, update["current_context"], str(date.today()))

    if update.get("history"):
        entries = update["history"]
        if isinstance(entries, dict):
            entries = [entries]
        if isinstance(entries, list):
            history = await load_history(user_id)
            changed = False
            for entry in entries:
                if isinstance(entry, dict) and "dish" in entry:
                    entry.setdefault("date", str(date.today()))
                    history.append(entry)
                    changed = True
            if changed:
                await save_history(user_id, history)

    await apply_pantry_update(user_id, update.get("pantry", []))


async def get_summary(user_id: int) -> dict:
    """Счётчики для карточек хаба Mini App: запасы, профиль и настройки одним запросом."""
    pantry = await list_pantry(user_id)
    tags = await list_tags(user_id)
    return {
        "pantry": {
            "total": len(pantry),
            "low": sum(1 for i in pantry if i["status"] == "low"),
            "to_buy": sum(1 for i in pantry if i["status"] == "to_buy"),
            "expiring": len(await check_expiring_soon(user_id)),
        },
        "profile": {kind: len(tags[kind]) for kind in ("restrictions", "equipment", "likes", "dislikes")},
        "settings": await get_settings(user_id),
    }
