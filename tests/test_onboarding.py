import pytest

from agent.chef import (
    ONBOARDING_STEPS,
    apply_onboarding_choice,
    current_onboarding_question,
    run_onboarding,
)
from memory.store import load_profile
from memory.users import approve_user

USER = 42


@pytest.fixture(autouse=True)
async def approved_user(database):
    await approve_user(USER)
FIELDS = ["likes", "dislikes", "restrictions", "servings", "cooking_time", "equipment"]


async def advance_to(field: str) -> None:
    """Проходит анкету текстом до шага `field` (вопрос уже задан и ждёт ответа)."""
    await run_onboarding(USER, "")
    for step in ONBOARDING_STEPS:
        if step.field == field:
            return
        await run_onboarding(USER, {"servings": "2", "cooking_time": "30"}.get(step.field, "x"))


def test_steps_order_and_kinds():
    assert [s.field for s in ONBOARDING_STEPS] == FIELDS
    kinds = {s.field: s.kind for s in ONBOARDING_STEPS}
    assert kinds["likes"] == kinds["dislikes"] == kinds["restrictions"] == "text"
    assert kinds["servings"] == kinds["cooking_time"] == "choice"
    assert kinds["equipment"] == "multiselect"


async def test_start_shows_first_question(database):
    view = await run_onboarding(USER, "")
    assert view.step is ONBOARDING_STEPS[0]
    assert "Какие кухни" in view.text
    assert (await load_profile(USER))["onboarding_step"] == 1


async def test_text_step_splits_by_commas(database):
    await run_onboarding(USER, "")
    view = await run_onboarding(USER, "итальянская, азиатская\nгрузинская")
    assert view.step.field == "dislikes"
    assert (await load_profile(USER))["likes"] == ["итальянская", "азиатская", "грузинская"]


async def test_current_question_is_read_only(database):
    await advance_to("servings")
    before = await load_profile(USER)
    view = await current_onboarding_question(USER)
    assert view.step.field == "servings"
    assert await load_profile(USER) == before


@pytest.mark.parametrize("raw, saved", [("3", "3"), ("на 2", "2"), ("1, иногда 2", "1")])
async def test_servings_text_is_normalized(database, raw, saved):
    await advance_to("servings")
    view = await run_onboarding(USER, raw)
    assert view.step.field == "cooking_time"
    assert (await load_profile(USER))["servings"] == saved


@pytest.mark.parametrize("raw", ["семья", "9", "0"])
async def test_servings_invalid_text_repeats_step(database, raw):
    await advance_to("servings")
    view = await run_onboarding(USER, raw)
    assert view.step.field == "servings"
    assert "кнопк" in view.text
    profile = await load_profile(USER)
    assert profile["onboarding_step"] == 4
    assert "servings" not in profile


@pytest.mark.parametrize(
    "raw, saved", [("30 мин", "30"), ("1 час", "60"), ("Не важно", "any"), ("15", "15")]
)
async def test_cooking_time_text_is_normalized(database, raw, saved):
    await advance_to("cooking_time")
    view = await run_onboarding(USER, raw)
    assert view.step.field == "equipment"
    assert (await load_profile(USER))["cooking_time"] == saved


async def test_cooking_time_invalid_text_repeats_step(database):
    await advance_to("cooking_time")
    view = await run_onboarding(USER, "минут 40")
    assert view.step.field == "cooking_time"
    assert "кнопк" in view.text
    assert (await load_profile(USER))["onboarding_step"] == 5


async def test_choice_callback_saves_preset_and_advances(database):
    await advance_to("servings")
    view = await apply_onboarding_choice(USER, "servings", "3")
    assert view.step.field == "cooking_time"
    profile = await load_profile(USER)
    assert profile["servings"] == "3"
    assert profile["onboarding_step"] == 5


async def test_choice_callback_invalid_value_repeats_step(database):
    await advance_to("servings")
    view = await apply_onboarding_choice(USER, "servings", "100")
    assert view.step.field == "servings"
    assert (await load_profile(USER))["onboarding_step"] == 4


async def test_stale_callback_is_ignored(database):
    await advance_to("cooking_time")
    # кнопка порций нажата, когда анкета уже на вопросе про время
    assert await apply_onboarding_choice(USER, "servings", "5") is None
    profile = await load_profile(USER)
    assert "servings" not in profile or profile["servings"] == "2"
    assert profile["onboarding_step"] == 5


async def test_double_tap_is_idempotent(database):
    await advance_to("servings")
    first = await apply_onboarding_choice(USER, "servings", "3")
    second = await apply_onboarding_choice(USER, "servings", "7")
    assert first is not None
    assert second is None
    assert (await load_profile(USER))["servings"] == "3"


async def test_callback_before_start_is_ignored(database):
    assert await apply_onboarding_choice(USER, "servings", "3") is None


async def test_equipment_callback_saves_list_and_finishes(database):
    await advance_to("equipment")
    view = await apply_onboarding_choice(USER, "equipment", ["духовка", "Блендер", "казан"])
    assert view.step is None
    assert "всё запомнил" in view.text
    profile = await load_profile(USER)
    assert profile["onboarding_done"] is True
    assert sorted(profile["equipment"]) == ["блендер", "духовка", "казан"]


async def test_equipment_empty_done_is_allowed(database):
    await advance_to("equipment")
    view = await apply_onboarding_choice(USER, "equipment", [])
    assert view.step is None
    profile = await load_profile(USER)
    assert profile["onboarding_done"] is True
    assert profile["equipment"] == []


async def test_callback_after_finish_is_ignored(database):
    await advance_to("equipment")
    await apply_onboarding_choice(USER, "equipment", ["духовка"])
    assert await apply_onboarding_choice(USER, "equipment", ["гриль"]) is None
    assert (await load_profile(USER))["equipment"] == ["духовка"]


async def test_equipment_text_is_legacy_comma_list(database):
    await advance_to("equipment")
    view = await run_onboarding(USER, "духовка, мультиварка")
    assert view.step is None
    assert (await load_profile(USER))["equipment"] == ["духовка", "мультиварка"]
