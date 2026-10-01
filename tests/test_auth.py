import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl, urlencode

import pytest

from webapp_api.auth import InitDataError, validate_init_data

TOKEN = "123456:TEST-TOKEN"


def sign(fields: dict, token: str = TOKEN) -> str:
    """Независимая реализация алгоритма из документации Telegram Mini Apps."""
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": h})


def make(user_id=42, auth_date=None, **extra) -> dict:
    return {
        "user": json.dumps({"id": user_id, "first_name": "Test", "username": "tester"}),
        "auth_date": str(int(auth_date if auth_date is not None else time.time())),
        "query_id": "AAH",
        **extra,
    }


def test_valid_signature_returns_user():
    user = validate_init_data(sign(make()), TOKEN, max_age=86400)
    assert user["id"] == 42
    assert user["username"] == "tester"


def test_wrong_token_rejected():
    with pytest.raises(InitDataError):
        validate_init_data(sign(make(), token="other:TOKEN"), TOKEN, max_age=86400)


def test_tampered_payload_rejected():
    signed = dict(parse_qsl(sign(make(user_id=42))))
    signed["user"] = make(user_id=43)["user"]  # подпись от user 42, подставлен user 43
    init = urlencode(signed)
    with pytest.raises(InitDataError):
        validate_init_data(init, TOKEN, max_age=86400)


def test_missing_hash_rejected():
    with pytest.raises(InitDataError):
        validate_init_data(urlencode(make()), TOKEN, max_age=86400)


def test_expired_auth_date_rejected():
    old = time.time() - 86400 - 10
    with pytest.raises(InitDataError):
        validate_init_data(sign(make(auth_date=old)), TOKEN, max_age=86400)


def test_missing_user_rejected():
    fields = make()
    del fields["user"]
    with pytest.raises(InitDataError):
        validate_init_data(sign(fields), TOKEN, max_age=86400)


def test_garbage_rejected():
    with pytest.raises(InitDataError):
        validate_init_data("", TOKEN, max_age=86400)
