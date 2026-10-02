from datetime import date

import pytest

import memory.db as db
from memory.store import (
    add_pantry_item,
    apply_pantry_update,
    check_expiring_soon,
    delete_pantry_item,
    list_pantry,
    load_pantry,
    update_pantry_item,
)
from memory.users import approve_user


@pytest.fixture
async def user(database):
    await approve_user(42)
    return 42


def by_name(items):
    return {i["name"]: i for i in items}


# --- Поведение apply_pantry_update, которое должно сохраниться при переписывании ---


async def test_legacy_new_item_defaults_to_have_with_added_date(user):
    await apply_pantry_update(user, [{"name": "Молоко"}])
    item = by_name(await load_pantry(user))["Молоко"]
    assert item["status"] == "have"
    assert item["added_date"] == str(date.today())


async def test_legacy_update_existing_item(user):
    await apply_pantry_update(user, [{"name": "Молоко", "quantity": "1 л"}])
    await apply_pantry_update(user, [{"name": "Молоко", "status": "low"}])
    item = by_name(await load_pantry(user))["Молоко"]
    assert item["status"] == "low"
    assert item["quantity"] == "1 л"


async def test_legacy_out_removes_item(user):
    await apply_pantry_update(user, [{"name": "Молоко"}, {"name": "Хлеб"}])
    await apply_pantry_update(user, [{"name": "Молоко", "status": "out"}])
    assert list(by_name(await load_pantry(user))) == ["Хлеб"]


async def test_legacy_out_for_unknown_item_is_noop(user):
    await apply_pantry_update(user, [{"name": "Ничего", "status": "out"}])
    assert await load_pantry(user) == []


async def test_legacy_expiry_and_quantity_only_set_when_given(user):
    await apply_pantry_update(user, [{"name": "Сыр", "expiry_date": "2030-01-01", "quantity": "200 г"}])
    await apply_pantry_update(user, [{"name": "Сыр", "status": "low"}])
    item = by_name(await load_pantry(user))["Сыр"]
    assert item["expiry_date"] == "2030-01-01"
    assert item["quantity"] == "200 г"


async def test_legacy_empty_and_nameless_changes_are_ignored(user):
    await apply_pantry_update(user, [])
    await apply_pantry_update(user, [{"status": "low"}, {"name": ""}])
    assert await load_pantry(user) == []


# --- to_buy: список покупок ---


async def test_to_buy_creates_item_with_to_buy_status(user):
    await apply_pantry_update(user, [{"name": "Молоко", "status": "to_buy"}])
    assert by_name(await load_pantry(user))["Молоко"]["status"] == "to_buy"


async def test_to_buy_moves_existing_item(user):
    await apply_pantry_update(user, [{"name": "Молоко", "quantity": "1 л"}])
    await apply_pantry_update(user, [{"name": "Молоко", "status": "to_buy"}])
    items = await load_pantry(user)
    assert len(items) == 1
    assert items[0]["status"] == "to_buy"


async def test_bought_item_goes_back_to_have(user):
    await apply_pantry_update(user, [{"name": "Молоко", "status": "to_buy"}])
    await apply_pantry_update(user, [{"name": "Молоко", "status": "have"}])
    assert by_name(await load_pantry(user))["Молоко"]["status"] == "have"


async def test_out_also_removes_item_from_shopping_list(user):
    await apply_pantry_update(user, [{"name": "Молоко", "status": "to_buy"}])
    await apply_pantry_update(user, [{"name": "Молоко", "status": "out"}])
    assert await load_pantry(user) == []


async def test_unknown_status_does_not_break_item(user):
    await apply_pantry_update(user, [{"name": "Молоко", "status": "bananas"}])
    assert by_name(await load_pantry(user))["Молоко"]["status"] == "have"
    await apply_pantry_update(user, [{"name": "Молоко", "status": "low"}])
    await apply_pantry_update(user, [{"name": "Молоко", "status": "bananas"}])
    assert by_name(await load_pantry(user))["Молоко"]["status"] == "low"


async def test_names_match_case_insensitively_for_cyrillic(user):
    await apply_pantry_update(user, [{"name": "Молоко"}])
    await apply_pantry_update(user, [{"name": "молоко", "status": "low"}])
    items = await load_pantry(user)
    assert len(items) == 1
    assert items[0]["status"] == "low"

    await apply_pantry_update(user, [{"name": "МОЛОКО", "status": "out"}])
    assert await load_pantry(user) == []


# --- Точечные операции ---


async def test_list_pantry_returns_ids(user):
    await apply_pantry_update(user, [{"name": "Молоко"}, {"name": "Хлеб"}])
    items = await list_pantry(user)
    assert all(isinstance(i["id"], int) for i in items)
    assert len({i["id"] for i in items}) == 2


async def test_add_pantry_item_returns_created_item(user):
    item = await add_pantry_item(user, "Сыр", status="low", quantity="200 г", expiry_date="2030-01-01")
    assert item["name"] == "Сыр"
    assert item["status"] == "low"
    assert item["quantity"] == "200 г"
    assert item["expiry_date"] == "2030-01-01"
    assert item["added_date"] == str(date.today())


async def test_add_existing_name_updates_instead_of_duplicating(user):
    first = await add_pantry_item(user, "Молоко")
    second = await add_pantry_item(user, "молоко", status="to_buy")
    assert second["id"] == first["id"]
    assert second["status"] == "to_buy"
    assert len(await list_pantry(user)) == 1


async def test_update_pantry_item_changes_only_given_fields(user):
    item = await add_pantry_item(user, "Сыр", quantity="200 г")
    updated = await update_pantry_item(user, item["id"], status="low")
    assert updated["status"] == "low"
    assert updated["quantity"] == "200 г"


async def test_update_pantry_item_can_clear_optional_fields(user):
    item = await add_pantry_item(user, "Сыр", quantity="200 г", expiry_date="2030-01-01")
    updated = await update_pantry_item(user, item["id"], quantity=None, expiry_date=None)
    assert updated["quantity"] is None
    assert updated["expiry_date"] is None


async def test_update_pantry_item_unknown_id_returns_none(user):
    assert await update_pantry_item(user, 999, status="low") is None


async def test_rename_to_existing_name_is_rejected(user):
    await add_pantry_item(user, "Молоко")
    item = await add_pantry_item(user, "Хлеб")
    with pytest.raises(ValueError):
        await update_pantry_item(user, item["id"], name="молоко")


async def test_delete_pantry_item(user):
    item = await add_pantry_item(user, "Молоко")
    assert await delete_pantry_item(user, item["id"]) is True
    assert await list_pantry(user) == []
    assert await delete_pantry_item(user, item["id"]) is False


async def test_other_users_item_is_not_touched(user):
    await approve_user(43)
    theirs = await add_pantry_item(43, "Молоко")

    assert await update_pantry_item(user, theirs["id"], status="low") is None
    assert await delete_pantry_item(user, theirs["id"]) is False
    assert (await list_pantry(43))[0]["status"] == "have"


# --- Остальные места, которых касается to_buy ---


async def test_expiring_check_skips_items_to_buy(user):
    await add_pantry_item(user, "Молоко", status="to_buy", expiry_date="2000-01-01")
    await add_pantry_item(user, "Сыр", expiry_date="2000-01-01")
    assert [i["name"] for i in await check_expiring_soon(user)] == ["Сыр"]


async def test_init_db_migrates_legacy_out_to_to_buy(user):
    conn = db.get_conn()
    await conn.execute(
        "INSERT INTO pantry_items (user_id, name, status) VALUES (?, ?, ?)", (user, "Молоко", "out")
    )
    await conn.commit()

    await db.close_db()
    await db.init_db()

    assert by_name(await load_pantry(user))["Молоко"]["status"] == "to_buy"
