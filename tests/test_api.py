import time
from tests.test_auth import make, sign
from memory.users import approve_user, reject_user, register_pending

TOKEN = "123456:TEST-TOKEN"


def headers(user_id=42, auth_date=None) -> dict:
    return {"Authorization": "tma " + sign(make(user_id=user_id, auth_date=auth_date))}


async def test_me_ok_for_approved(client):
    await approve_user(42)
    r = await client.get("/api/me", headers=headers())
    assert r.status_code == 200
    assert r.json() == {"user_id": 42, "username": "tester"}


async def test_me_without_header_is_401(client):
    assert (await client.get("/api/me")).status_code == 401


async def test_me_wrong_scheme_is_401(client):
    r = await client.get("/api/me", headers={"Authorization": "Bearer abc"})
    assert r.status_code == 401


async def test_me_bad_signature_is_401(client):
    await approve_user(42)
    r = await client.get("/api/me", headers={"Authorization": "tma " + sign(make(), token="x:y")})
    assert r.status_code == 401


async def test_me_expired_is_401(client):
    await approve_user(42)
    r = await client.get("/api/me", headers=headers(auth_date=time.time() - 10**6))
    assert r.status_code == 401


async def test_me_unknown_user_is_403(client):
    assert (await client.get("/api/me", headers=headers())).status_code == 403


async def test_me_pending_is_403(client):
    await register_pending(42, "tester")
    assert (await client.get("/api/me", headers=headers())).status_code == 403


async def test_me_rejected_is_403(client):
    await reject_user(42)
    assert (await client.get("/api/me", headers=headers())).status_code == 403
