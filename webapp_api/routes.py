from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, StringConstraints

from config import EQUIPMENT_OPTIONS, EXPIRY_WARNING_DAYS
from memory.store import (
    PantryNameTaken,
    add_pantry_item,
    add_tag,
    delete_pantry_item,
    get_settings,
    get_summary,
    list_pantry,
    list_tags,
    remove_tag,
    set_settings,
    update_pantry_item,
)
from webapp_api.deps import current_user

router = APIRouter(prefix="/api")


class SettingsPatch(BaseModel):
    servings: int | None = Field(default=None, ge=1, le=8)
    cooking_time: Literal["15", "30", "60", "any"] | None = None


PantryName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
PantryQuantity = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
PantryStatus = Literal["have", "low", "to_buy"]


class PantryCreate(BaseModel):
    name: PantryName
    status: PantryStatus = "have"
    quantity: PantryQuantity | None = None
    expiry_date: date | None = None


class PantryPatch(BaseModel):
    name: PantryName | None = None
    status: PantryStatus | None = None
    quantity: PantryQuantity | None = None
    expiry_date: date | None = None


class TagCreate(BaseModel):
    kind: Literal["likes", "dislikes", "restrictions", "equipment"]
    value: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


@router.get("/me")
async def me(user: dict = Depends(current_user)):
    return {"user_id": int(user["id"]), "username": user.get("username")}


@router.get("/summary")
async def read_summary(user: dict = Depends(current_user)):
    return await get_summary(int(user["id"]))


@router.get("/settings")
async def read_settings(user: dict = Depends(current_user)):
    return await get_settings(int(user["id"]))


@router.patch("/settings")
async def patch_settings(body: SettingsPatch, user: dict = Depends(current_user)):
    if body.servings is None and body.cooking_time is None:
        raise HTTPException(status_code=422, detail="Нужно передать servings или cooking_time")
    user_id = int(user["id"])
    await set_settings(user_id, servings=body.servings, cooking_time=body.cooking_time)
    return await get_settings(user_id)


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


@router.get("/pantry")
async def read_pantry(user: dict = Depends(current_user)):
    return {"items": await list_pantry(int(user["id"])), "expiry_warning_days": EXPIRY_WARNING_DAYS}


@router.post("/pantry", status_code=201)
async def create_pantry_item(body: PantryCreate, user: dict = Depends(current_user)):
    return await add_pantry_item(
        int(user["id"]),
        body.name,
        status=body.status,
        quantity=body.quantity,
        expiry_date=_iso(body.expiry_date),
    )


@router.patch("/pantry/{item_id}")
async def patch_pantry_item(item_id: int, body: PantryPatch, user: dict = Depends(current_user)):
    # передать можно только то, что клиент прислал; null у quantity/expiry_date очищает поле
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=422, detail="Нужно передать хотя бы одно поле")
    if fields.get("name", "") is None or fields.get("status", "") is None:
        raise HTTPException(status_code=422, detail="name и status нельзя очистить")
    if "expiry_date" in fields:
        fields["expiry_date"] = _iso(fields["expiry_date"])

    try:
        item = await update_pantry_item(int(user["id"]), item_id, **fields)
    except PantryNameTaken:
        raise HTTPException(status_code=409, detail="Позиция с таким названием уже есть")
    if item is None:
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    return item


@router.delete("/pantry/{item_id}", status_code=204)
async def remove_pantry_item(item_id: int, user: dict = Depends(current_user)):
    if not await delete_pantry_item(int(user["id"]), item_id):
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    return Response(status_code=204)


@router.get("/profile")
async def read_profile(user: dict = Depends(current_user)):
    return {**await list_tags(int(user["id"])), "equipment_options": EQUIPMENT_OPTIONS}


@router.post("/profile/tags", status_code=201)
async def create_tag(body: TagCreate, user: dict = Depends(current_user)):
    return await add_tag(int(user["id"]), body.kind, body.value)


@router.delete("/profile/tags/{tag_id}", status_code=204)
async def delete_tag(tag_id: int, user: dict = Depends(current_user)):
    if not await remove_tag(int(user["id"]), tag_id):
        raise HTTPException(status_code=404, detail="Тег не найден")
    return Response(status_code=204)
