from datetime import date

import pytest

from memory.store import apply_memory_update, load_history, load_pantry, load_profile, save_profile
from memory.users import approve_user


@pytest.fixture
async def user(database):
    await approve_user(42)
    return 42


async def test_adds_new_tags_to_each_kind(user):
    await apply_memory_update(
        user,
        {"likes": ["сыр"], "dislikes": ["лук"], "restrictions": ["без глютена"], "equipment": ["духовка"]},
    )
    profile = await load_profile(user)
    assert profile["likes"] == ["сыр"]
    assert profile["dislikes"] == ["лук"]
    assert profile["restrictions"] == ["без глютена"]
    assert profile["equipment"] == ["духовка"]


async def test_does_not_duplicate_existing_tag(user):
    await apply_memory_update(user, {"likes": ["сыр"]})
    await apply_memory_update(user, {"likes": ["сыр", "хлеб"]})
    assert (await load_profile(user))["likes"] == ["сыр", "хлеб"]


async def test_strips_add_prefix_from_llm(user):
    await apply_memory_update(user, {"likes": ["добавить: сыр"]})
    assert (await load_profile(user))["likes"] == ["сыр"]


async def test_ignores_blank_tags(user):
    await apply_memory_update(user, {"likes": ["", "   ", "добавить: "]})
    assert (await load_profile(user))["likes"] == []


async def test_saves_current_context_with_today(user):
    await apply_memory_update(user, {"current_context": "готовлю ужин на двоих"})
    context = (await load_profile(user))["current_context"]
    assert context == {"notes": "готовлю ужин на двоих", "updated": str(date.today())}


async def test_appends_history_entry_with_default_date(user):
    await apply_memory_update(user, {"history": {"dish": "борщ", "rating": "понравилось"}})
    history = await load_history(user)
    assert history == [{"dish": "борщ", "rating": "понравилось", "date": str(date.today())}]


async def test_empty_update_changes_nothing(user):
    await save_profile(user, {"onboarding_done": True, "likes": ["сыр"], "servings": "4"})
    await apply_memory_update(user, {})
    profile = await load_profile(user)
    assert profile["onboarding_done"] is True
    assert profile["likes"] == ["сыр"]
    assert profile["servings"] == "4"


async def test_keeps_rest_of_profile(user):
    await save_profile(
        user,
        {"onboarding_done": True, "onboarding_step": 6, "servings": "4", "cooking_time": "30", "likes": ["сыр"]},
    )
    await apply_memory_update(user, {"dislikes": ["лук"]})
    profile = await load_profile(user)
    assert profile["onboarding_done"] is True
    assert profile["onboarding_step"] == 6
    assert profile["servings"] == "4"
    assert profile["cooking_time"] == "30"
    assert profile["likes"] == ["сыр"]


async def test_passes_pantry_changes_through(user):
    await apply_memory_update(user, {"pantry": [{"name": "Молоко", "status": "to_buy"}]})
    assert (await load_pantry(user))[0]["status"] == "to_buy"
