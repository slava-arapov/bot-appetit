from fastapi import APIRouter, Depends

from webapp_api.deps import current_user

router = APIRouter(prefix="/api")


@router.get("/me")
async def me(user: dict = Depends(current_user)):
    return {"user_id": int(user["id"]), "username": user.get("username")}
