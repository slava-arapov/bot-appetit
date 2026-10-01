import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


class InitDataError(Exception):
    """initData не прошёл проверку (подпись, срок, структура)."""


def validate_init_data(init_data: str, bot_token: str, max_age: int) -> dict:
    """Проверяет подпись Telegram initData и возвращает объект user.

    Алгоритм: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    fields = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = fields.pop("hash", None)
    if not received_hash:
        raise InitDataError("нет hash")

    check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise InitDataError("неверная подпись")

    try:
        auth_date = int(fields["auth_date"])
    except (KeyError, ValueError):
        raise InitDataError("нет auth_date")
    if time.time() - auth_date > max_age:
        raise InitDataError("initData устарел")

    try:
        user = json.loads(fields["user"])
        int(user["id"])
    except (KeyError, ValueError, TypeError):
        raise InitDataError("нет user")
    return user
