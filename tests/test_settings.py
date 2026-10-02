import pytest

from memory.store import (
    describe_cooking_time,
    describe_servings,
    get_settings,
    load_profile,
    normalize_cooking_time,
    normalize_servings,
    save_profile,
    set_settings,
)
from memory.users import approve_user
from tests.test_api import headers


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("4", 4),
        ("2 человека", 2),
        ("на троих — 3", 3),
        ("8", 8),
        ("9", None),
        ("0", None),
        ("семья", None),
        ("1, иногда 2", 1),
        ("на 1", 1),
        ("", None),
        (None, None),
    ],
)
def test_normalize_servings(raw, expected):
    assert normalize_servings(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("15", "15"),
        ("30", "30"),
        ("60", "60"),
        ("any", "any"),
        ("30 минут", "30"),
        ("не важно", "any"),
        ("Не важно", "any"),
        ("неважно", "any"),
        ("Неважно!", "any"),
        ("не важно.", "any"),
        ("не важно, любое", "any"),
        ("время не важно", "any"),
        ("до 30 минут", "30"),
        ("30 мин", "30"),
        ("1 час", "60"),
        ("час", "60"),
        ("1 ч", "60"),
        ("до часа", "60"),
        ("Не более 1 часа", "60"),
        ("60 минут", "60"),
        ("до получаса", None),
        ("20 минут", None),
        ("40 минут", None),
        ("полтора часа", None),
        ("2 часа", None),
        ("30 часов", None),
        ("15 часов в неделю", None),
        ("2 часа 30 минут", None),
        ("1 час 30 минут", None),
        ("30 минут", "30"),
        ("Как можно меньше", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_cooking_time(raw, expected):
    assert normalize_cooking_time(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1", "1 порция"),
        ("2", "2 порции"),
        ("4", "4 порции"),
        ("5", "5 порций"),
        ("8", "8 порций"),
        ("несколько", "несколько"),
        (None, None),
    ],
)
def test_describe_servings(raw, expected):
    assert describe_servings(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("15", "до 15 минут"),
        ("60", "до 60 минут"),
        ("any", "время не важно"),
        ("до получаса", "до получаса"),
        (None, None),
    ],
)
def test_describe_cooking_time(raw, expected):
    assert describe_cooking_time(raw) == expected


async def test_get_settings_empty_when_no_profile(database):
    await approve_user(42)
    assert await get_settings(42) == {"servings": None, "cooking_time": None}


async def test_set_then_get_settings(database):
    await approve_user(42)
    await set_settings(42, servings=4, cooking_time="30")
    assert await get_settings(42) == {"servings": 4, "cooking_time": "30"}


async def test_set_settings_is_partial(database):
    await approve_user(42)
    await set_settings(42, servings=4, cooking_time="30")
    await set_settings(42, servings=2)
    assert await get_settings(42) == {"servings": 2, "cooking_time": "30"}


async def test_set_settings_keeps_rest_of_profile(database):
    await approve_user(42)
    await save_profile(42, {"onboarding_done": True, "likes": ["сыр"], "servings": "2 человека"})
    await set_settings(42, cooking_time="15")

    profile = await load_profile(42)
    assert profile["onboarding_done"] is True
    assert profile["likes"] == ["сыр"]
    assert await get_settings(42) == {"servings": 2, "cooking_time": "15"}


async def test_get_settings_normalizes_legacy_free_text(database):
    await approve_user(42)
    await save_profile(42, {"servings": "2 человека", "cooking_time": "до получаса"})
    assert await get_settings(42) == {"servings": 2, "cooking_time": None}


async def test_api_get_settings_empty(client):
    await approve_user(42)
    r = await client.get("/api/settings", headers=headers())
    assert r.status_code == 200
    assert r.json() == {"servings": None, "cooking_time": None}


async def test_api_patch_settings_roundtrip(client):
    await approve_user(42)
    r = await client.patch("/api/settings", json={"servings": 4}, headers=headers())
    assert r.status_code == 200
    assert r.json() == {"servings": 4, "cooking_time": None}

    r = await client.patch("/api/settings", json={"cooking_time": "any"}, headers=headers())
    assert r.json() == {"servings": 4, "cooking_time": "any"}

    r = await client.get("/api/settings", headers=headers())
    assert r.json() == {"servings": 4, "cooking_time": "any"}


async def test_api_patch_settings_only_touches_own_user(client):
    await approve_user(42)
    await approve_user(43)
    await client.patch("/api/settings", json={"servings": 4}, headers=headers(user_id=42))

    r = await client.get("/api/settings", headers=headers(user_id=43))
    assert r.json() == {"servings": None, "cooking_time": None}


@pytest.mark.parametrize(
    "body",
    [{}, {"servings": 9}, {"servings": 0}, {"cooking_time": "45"}, {"servings": "много"}],
)
async def test_api_patch_settings_rejects_bad_body(client, body):
    await approve_user(42)
    r = await client.patch("/api/settings", json=body, headers=headers())
    assert r.status_code == 422


async def test_api_settings_without_auth_is_401(client):
    assert (await client.get("/api/settings")).status_code == 401
    assert (await client.patch("/api/settings", json={"servings": 2})).status_code == 401


def test_equipment_options_are_unique_lowercase():
    from config import EQUIPMENT_OPTIONS

    assert len(EQUIPMENT_OPTIONS) == len(set(EQUIPMENT_OPTIONS))
    assert all(option == option.strip().lower() for option in EQUIPMENT_OPTIONS)
    assert {"духовка", "плита", "блендер"} <= set(EQUIPMENT_OPTIONS)
