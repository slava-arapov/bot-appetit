import pytest

from config import EXPIRY_WARNING_DAYS
from memory.store import add_pantry_item, list_pantry
from memory.users import approve_user
from tests.test_api import headers


@pytest.fixture
async def user(database):
    await approve_user(42)
    return 42


async def test_get_empty_pantry(client, user):
    r = await client.get("/api/pantry", headers=headers())
    assert r.status_code == 200
    assert r.json() == {"items": [], "expiry_warning_days": EXPIRY_WARNING_DAYS}


async def test_get_returns_items_with_ids(client, user):
    created = await add_pantry_item(user, "Молоко", status="to_buy", quantity="1 л")
    r = await client.get("/api/pantry", headers=headers())
    assert r.json()["items"] == [
        {
            "id": created["id"],
            "name": "Молоко",
            "status": "to_buy",
            "quantity": "1 л",
            "expiry_date": None,
            "added_date": created["added_date"],
        }
    ]


async def test_post_creates_item(client, user):
    r = await client.post(
        "/api/pantry",
        json={"name": "  Сыр ", "quantity": "200 г", "expiry_date": "2030-01-01"},
        headers=headers(),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Сыр"
    assert body["status"] == "have"
    assert body["quantity"] == "200 г"
    assert body["expiry_date"] == "2030-01-01"
    assert len(await list_pantry(user)) == 1


async def test_post_existing_name_does_not_duplicate(client, user):
    first = (await client.post("/api/pantry", json={"name": "Молоко"}, headers=headers())).json()
    second = await client.post(
        "/api/pantry", json={"name": "молоко", "status": "to_buy"}, headers=headers()
    )
    assert second.json()["id"] == first["id"]
    assert second.json()["status"] == "to_buy"
    assert len(await list_pantry(user)) == 1


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": ""},
        {"name": "   "},
        {"name": "х" * 81},
        {"name": "Сыр", "status": "out"},
        {"name": "Сыр", "status": "bananas"},
        {"name": "Сыр", "expiry_date": "завтра"},
        {"name": "Сыр", "quantity": "х" * 41},
    ],
)
async def test_post_rejects_bad_body(client, user, body):
    r = await client.post("/api/pantry", json=body, headers=headers())
    assert r.status_code == 422


async def test_patch_changes_only_given_fields(client, user):
    item = await add_pantry_item(user, "Сыр", quantity="200 г")
    r = await client.patch(f"/api/pantry/{item['id']}", json={"status": "low"}, headers=headers())
    assert r.status_code == 200
    assert r.json()["status"] == "low"
    assert r.json()["quantity"] == "200 г"


async def test_patch_null_clears_optional_fields(client, user):
    item = await add_pantry_item(user, "Сыр", quantity="200 г", expiry_date="2030-01-01")
    r = await client.patch(
        f"/api/pantry/{item['id']}", json={"quantity": None, "expiry_date": None}, headers=headers()
    )
    assert r.json()["quantity"] is None
    assert r.json()["expiry_date"] is None


async def test_patch_renames_item(client, user):
    item = await add_pantry_item(user, "Сыр")
    r = await client.patch(f"/api/pantry/{item['id']}", json={"name": "Сыр твёрдый"}, headers=headers())
    assert r.json()["name"] == "Сыр твёрдый"


async def test_patch_rename_to_existing_name_is_409(client, user):
    await add_pantry_item(user, "Молоко")
    item = await add_pantry_item(user, "Хлеб")
    r = await client.patch(f"/api/pantry/{item['id']}", json={"name": "МОЛОКО"}, headers=headers())
    assert r.status_code == 409


@pytest.mark.parametrize(
    "body", [{}, {"status": "out"}, {"status": None}, {"name": None}, {"name": " "}]
)
async def test_patch_rejects_bad_body(client, user, body):
    item = await add_pantry_item(user, "Сыр")
    r = await client.patch(f"/api/pantry/{item['id']}", json=body, headers=headers())
    assert r.status_code == 422


async def test_patch_unknown_id_is_404(client, user):
    r = await client.patch("/api/pantry/999", json={"status": "low"}, headers=headers())
    assert r.status_code == 404


async def test_delete_item(client, user):
    item = await add_pantry_item(user, "Молоко")
    r = await client.delete(f"/api/pantry/{item['id']}", headers=headers())
    assert r.status_code == 204
    assert r.content == b""
    assert await list_pantry(user) == []

    again = await client.delete(f"/api/pantry/{item['id']}", headers=headers())
    assert again.status_code == 404


async def test_other_users_items_are_invisible_and_untouchable(client, user):
    await approve_user(43)
    theirs = await add_pantry_item(43, "Молоко")

    assert (await client.get("/api/pantry", headers=headers())).json()["items"] == []
    assert (
        await client.patch(f"/api/pantry/{theirs['id']}", json={"status": "low"}, headers=headers())
    ).status_code == 404
    assert (await client.delete(f"/api/pantry/{theirs['id']}", headers=headers())).status_code == 404
    assert (await list_pantry(43))[0]["status"] == "have"


async def test_pantry_without_auth_is_401(client):
    assert (await client.get("/api/pantry")).status_code == 401
    assert (await client.post("/api/pantry", json={"name": "x"})).status_code == 401
    assert (await client.patch("/api/pantry/1", json={"status": "low"})).status_code == 401
    assert (await client.delete("/api/pantry/1")).status_code == 401
