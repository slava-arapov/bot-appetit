import pytest

import memory.db as db

from memory.store import (
    add_tag,
    apply_memory_update,
    list_tags,
    remove_tag,
    save_profile,
)
from memory.users import approve_user
from tests.test_api import headers

KINDS = ["restrictions", "equipment", "likes", "dislikes"]


@pytest.fixture
async def user(database):
    await approve_user(42)
    return 42


# --- Хранилище ---


async def test_list_tags_empty_has_all_kinds(user):
    assert await list_tags(user) == {kind: [] for kind in KINDS}


async def test_add_tag_returns_created_tag(user):
    tag = await add_tag(user, "likes", "  сыр ")
    assert tag == {"id": tag["id"], "kind": "likes", "value": "сыр"}
    assert (await list_tags(user))["likes"] == [{"id": tag["id"], "value": "сыр"}]


async def test_add_existing_tag_returns_it_without_duplicating(user):
    first = await add_tag(user, "likes", "Сыр")
    second = await add_tag(user, "likes", "сыр")
    assert second["id"] == first["id"]
    assert len((await list_tags(user))["likes"]) == 1


async def test_same_value_in_different_kinds_is_allowed(user):
    await add_tag(user, "likes", "лук")
    await add_tag(user, "dislikes", "лук")
    tags = await list_tags(user)
    assert len(tags["likes"]) == 1
    assert len(tags["dislikes"]) == 1


async def test_add_tag_rejects_unknown_kind(user):
    with pytest.raises(ValueError):
        await add_tag(user, "colors", "красный")


async def test_tags_keep_insertion_order(user):
    for value in ["б", "а", "в"]:
        await add_tag(user, "likes", value)
    assert [t["value"] for t in (await list_tags(user))["likes"]] == ["б", "а", "в"]


async def test_remove_tag(user):
    tag = await add_tag(user, "likes", "сыр")
    assert await remove_tag(user, tag["id"]) is True
    assert (await list_tags(user))["likes"] == []
    assert await remove_tag(user, tag["id"]) is False


async def test_other_users_tag_is_not_removed(user):
    await approve_user(43)
    theirs = await add_tag(43, "likes", "сыр")
    assert await remove_tag(user, theirs["id"]) is False
    assert len((await list_tags(43))["likes"]) == 1


async def test_tag_ids_survive_memory_update_from_llm(user):
    cheese = await add_tag(user, "likes", "сыр")

    await apply_memory_update(user, {"likes": ["хлеб"], "current_context": "ужин"})

    ids = {t["value"]: t["id"] for t in (await list_tags(user))["likes"]}
    assert ids["сыр"] == cheese["id"]
    assert "хлеб" in ids


async def test_memory_update_does_not_duplicate_tag_with_other_case(user):
    await add_tag(user, "likes", "Сыр")
    await apply_memory_update(user, {"likes": ["сыр"]})
    assert len((await list_tags(user))["likes"]) == 1


async def test_onboarding_save_still_replaces_tags(user):
    await add_tag(user, "likes", "сыр")
    await save_profile(user, {"likes": ["хлеб"]})
    assert [t["value"] for t in (await list_tags(user))["likes"]] == ["хлеб"]


# --- API ---


async def test_api_get_profile_empty(client, user):
    r = await client.get("/api/profile", headers=headers())
    assert r.status_code == 200
    assert r.json() == {kind: [] for kind in KINDS}


async def test_api_get_profile_returns_tags_with_ids(client, user):
    tag = await add_tag(user, "equipment", "духовка")
    r = await client.get("/api/profile", headers=headers())
    assert r.json()["equipment"] == [{"id": tag["id"], "value": "духовка"}]


async def test_api_post_creates_tag(client, user):
    r = await client.post("/api/profile/tags", json={"kind": "likes", "value": " сыр "}, headers=headers())
    assert r.status_code == 201
    assert r.json()["kind"] == "likes"
    assert r.json()["value"] == "сыр"
    assert len((await list_tags(user))["likes"]) == 1


async def test_api_post_existing_tag_returns_same_one(client, user):
    first = (await client.post("/api/profile/tags", json={"kind": "likes", "value": "Сыр"}, headers=headers())).json()
    second = (await client.post("/api/profile/tags", json={"kind": "likes", "value": "сыр"}, headers=headers())).json()
    assert second["id"] == first["id"]
    assert len((await list_tags(user))["likes"]) == 1


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"kind": "likes"},
        {"kind": "likes", "value": ""},
        {"kind": "likes", "value": "   "},
        {"kind": "likes", "value": "х" * 41},
        {"kind": "colors", "value": "красный"},
    ],
)
async def test_api_post_rejects_bad_body(client, user, body):
    r = await client.post("/api/profile/tags", json=body, headers=headers())
    assert r.status_code == 422


async def test_api_delete_tag(client, user):
    tag = await add_tag(user, "likes", "сыр")
    r = await client.delete(f"/api/profile/tags/{tag['id']}", headers=headers())
    assert r.status_code == 204
    assert (await list_tags(user))["likes"] == []

    again = await client.delete(f"/api/profile/tags/{tag['id']}", headers=headers())
    assert again.status_code == 404


async def test_api_other_users_tags_are_invisible_and_untouchable(client, user):
    await approve_user(43)
    theirs = await add_tag(43, "likes", "сыр")

    assert (await client.get("/api/profile", headers=headers())).json()["likes"] == []
    r = await client.delete(f"/api/profile/tags/{theirs['id']}", headers=headers())
    assert r.status_code == 404
    assert len((await list_tags(43))["likes"]) == 1


async def test_api_profile_without_auth_is_401(client):
    assert (await client.get("/api/profile")).status_code == 401
    assert (await client.post("/api/profile/tags", json={"kind": "likes", "value": "x"})).status_code == 401
    assert (await client.delete("/api/profile/tags/1")).status_code == 401


# --- Теги хранятся в нижнем регистре ---


async def test_add_tag_stores_lowercase(user):
    tag = await add_tag(user, "likes", "  Сыр ")
    assert tag["value"] == "сыр"
    assert (await list_tags(user))["likes"][0]["value"] == "сыр"


async def test_memory_update_stores_tags_in_lowercase(user):
    await apply_memory_update(user, {"likes": ["Сыр"], "equipment": ["Аэрогриль"]})
    tags = await list_tags(user)
    assert tags["likes"][0]["value"] == "сыр"
    assert tags["equipment"][0]["value"] == "аэрогриль"


async def test_onboarding_save_lowercases_and_dedupes_tags(user):
    await save_profile(user, {"likes": ["Сыр", "сыр", "Хлеб"]})
    assert [t["value"] for t in (await list_tags(user))["likes"]] == ["сыр", "хлеб"]


async def test_api_post_returns_lowercase_value(client, user):
    r = await client.post("/api/profile/tags", json={"kind": "equipment", "value": "Духовка"}, headers=headers())
    assert r.json()["value"] == "духовка"


async def test_init_db_lowercases_existing_tags_and_merges_duplicates(user):
    await approve_user(43)
    conn = db.get_conn()
    rows = [
        (user, "equipment", "Духовка"),
        (user, "equipment", "духовка"),  # дубль после приведения к нижнему регистру
        (user, "likes", "Сыр"),
        (43, "likes", "Сыр"),  # у другого пользователя это отдельный тег
    ]
    await conn.executemany("INSERT INTO profile_tags (user_id, kind, value) VALUES (?, ?, ?)", rows)
    await conn.commit()

    await db.close_db()
    await db.init_db()

    mine = await list_tags(user)
    assert [t["value"] for t in mine["equipment"]] == ["духовка"]
    assert [t["value"] for t in mine["likes"]] == ["сыр"]
    assert [t["value"] for t in (await list_tags(43))["likes"]] == ["сыр"]
