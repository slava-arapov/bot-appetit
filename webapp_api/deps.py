from fastapi import Header, HTTPException

from config import INITDATA_MAX_AGE, TELEGRAM_TOKEN
from memory.users import get_user_status
from webapp_api.auth import InitDataError, validate_init_data


async def current_user(authorization: str | None = Header(default=None)) -> dict:
    """Пользователь из заголовка `Authorization: tma <initData>`; только approved."""
    scheme, _, init_data = (authorization or "").partition(" ")
    if scheme != "tma" or not init_data:
        raise HTTPException(401, "Нужен заголовок Authorization: tma <initData>")
    try:
        user = validate_init_data(init_data, TELEGRAM_TOKEN, INITDATA_MAX_AGE)
    except InitDataError as e:
        raise HTTPException(401, str(e))
    if await get_user_status(int(user["id"])) != "approved":
        raise HTTPException(403, "Доступ не одобрен")
    return user
