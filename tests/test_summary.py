import pytest

from memory.store import add_pantry_item, add_tag, get_summary, set_settings
from memory.users import approve_user
from tests.test_api import headers


@pytest.fixture
async def user(database):
    await approve_user(42)
    return 42


EMPTY = {
    "pantry": {"total": 0, "low": 0, "to_buy": 0, "expiring": 0},
    "profile": {"restrictions": 0, "equipment": 0, "likes": 0, "dislikes": 0},
    "settings": {"servings": None, "cooking_time": None},
}


async def test_summary_of_new_user_is_empty(user):
    assert await get_summary(user) == EMPTY


async def test_summary_counts_pantry_by_status(user):
    await add_pantry_item(user, "Молоко")
    await add_pantry_item(user, "Сыр", status="low")
    await add_pantry_item(user, "Масло", status="low")
    await add_pantry_item(user, "Хлеб", status="to_buy")

    pantry = (await get_summary(user))["pantry"]
    assert pantry == {"total": 4, "low": 2, "to_buy": 1, "expiring": 0}


async def test_summary_expiring_ignores_shopping_list(user):
    await add_pantry_item(user, "Йогурт", expiry_date="2000-01-01")
    await add_pantry_item(user, "Молоко", status="to_buy", expiry_date="2000-01-01")
    await add_pantry_item(user, "Рис", expiry_date="2999-01-01")

    assert (await get_summary(user))["pantry"]["expiring"] == 1


async def test_summary_counts_tags_per_kind(user):
    await add_tag(user, "likes", "сыр")
    await add_tag(user, "likes", "хлеб")
    await add_tag(user, "restrictions", "без глютена")
    await add_tag(user, "equipment", "духовка")

    assert (await get_summary(user))["profile"] == {
        "restrictions": 1,
        "equipment": 1,
        "likes": 2,
        "dislikes": 0,
    }


async def test_summary_includes_normalized_settings(user):
    await set_settings(user, servings=4, cooking_time="30")
    assert (await get_summary(user))["settings"] == {"servings": 4, "cooking_time": "30"}


async def test_summary_is_per_user(user):
    await approve_user(43)
    await add_pantry_item(43, "Молоко", status="to_buy")
    assert (await get_summary(user)) == EMPTY


async def test_api_summary(client, user):
    await add_pantry_item(user, "Сыр", status="low")
    r = await client.get("/api/summary", headers=headers())
    assert r.status_code == 200
    assert r.json()["pantry"]["low"] == 1
    assert set(r.json()) == {"pantry", "profile", "settings"}


async def test_api_summary_without_auth_is_401(client):
    assert (await client.get("/api/summary")).status_code == 401
