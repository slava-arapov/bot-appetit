from agent.chef import ONBOARDING_STEPS
from bot.keyboards import (
    equipment_keyboard,
    keyboard_for,
    servings_keyboard,
    time_keyboard,
)
from config import EQUIPMENT_OPTIONS
from memory.store import COOKING_TIME_PRESETS, normalize_cooking_time, normalize_servings


def callbacks(markup):
    return [[b.callback_data for b in row] for row in markup.inline_keyboard]


def labels(markup):
    return [[b.text for b in row] for row in markup.inline_keyboard]


def step(field):
    return next(s for s in ONBOARDING_STEPS if s.field == field)


def test_servings_keyboard_has_eight_buttons_in_two_rows():
    rows = callbacks(servings_keyboard())
    assert rows == [[f"onb:servings:{n}" for n in range(1, 5)], [f"onb:servings:{n}" for n in range(5, 9)]]
    assert all(normalize_servings(data.rsplit(":", 1)[1]) for row in rows for data in row)


def test_time_keyboard_matches_presets():
    markup = time_keyboard()
    values = [data.rsplit(":", 1)[1] for data in callbacks(markup)[0]]
    assert values == list(COOKING_TIME_PRESETS)
    assert all(normalize_cooking_time(v) == v for v in values)
    assert labels(markup) == [["15 мин", "30 мин", "1 час", "Не важно"]]


def test_equipment_keyboard_marks_selected_and_has_controls():
    markup = equipment_keyboard({0, 2})
    flat = [b for row in markup.inline_keyboard for b in row]
    options = flat[: len(EQUIPMENT_OPTIONS)]
    assert [b.text for b in options][0] == f"✅ {EQUIPMENT_OPTIONS[0]}"
    assert [b.text for b in options][1] == EQUIPMENT_OPTIONS[1]
    assert [b.text for b in options][2] == f"✅ {EQUIPMENT_OPTIONS[2]}"
    assert [b.callback_data for b in options] == [f"onb:eq:{i}" for i in range(len(EQUIPMENT_OPTIONS))]
    assert [b.callback_data for b in markup.inline_keyboard[-1]] == ["onb:eq:other", "onb:eq:done"]
    assert all(len(row) <= 2 for row in markup.inline_keyboard)


def test_callback_data_fits_telegram_limit():
    for markup in (servings_keyboard(), time_keyboard(), equipment_keyboard(set())):
        for row in callbacks(markup):
            assert all(len(data.encode()) <= 64 for data in row)


def test_keyboard_for_each_step_kind():
    assert keyboard_for(step("likes")) is None
    assert keyboard_for(step("restrictions")) is None
    assert callbacks(keyboard_for(step("servings"))) == callbacks(servings_keyboard())
    assert callbacks(keyboard_for(step("cooking_time"))) == callbacks(time_keyboard())
    assert callbacks(keyboard_for(step("equipment"), {1})) == callbacks(equipment_keyboard({1}))
    assert keyboard_for(None) is None
