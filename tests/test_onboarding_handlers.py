from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.error import BadRequest

from agent.chef import apply_onboarding_choice, run_onboarding
from bot import handlers
from config import EQUIPMENT_OPTIONS
from memory.store import load_profile
from memory.users import approve_user

USER = 42
STRANGER = 99


@pytest.fixture(autouse=True)
async def approved_user(database):
    await approve_user(USER)


def make_context(user_data=None):
    bot = SimpleNamespace(
        send_message=AsyncMock(return_value=SimpleNamespace(message_id=100)),
        edit_message_text=AsyncMock(),
        edit_message_reply_markup=AsyncMock(),
        send_chat_action=AsyncMock(),
    )
    return SimpleNamespace(bot=bot, user_data={} if user_data is None else user_data)


def fresh_equipment_state():
    return {"onb_equipment": set(), "onb_custom": []}


def make_callback(data, user_id=USER, message_id=7, text="Вопрос"):
    query = SimpleNamespace(
        data=data,
        from_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(chat_id=user_id, message_id=message_id, text=text),
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
        edit_message_reply_markup=AsyncMock(),
    )
    return SimpleNamespace(callback_query=query), query


def make_text(text, user_id=USER):
    message = SimpleNamespace(text=text, reply_text=AsyncMock())
    return SimpleNamespace(
        message=message,
        effective_user=SimpleNamespace(id=user_id, username="u", full_name="U"),
        effective_chat=SimpleNamespace(id=user_id),
    )


async def advance_to(field):
    """Проходит анкету до шага `field`: вопрос задан и ждёт ответа."""
    await run_onboarding(USER, "")
    order = ["likes", "dislikes", "restrictions", "servings", "cooking_time", "equipment"]
    for current in order[: order.index(field)]:
        await run_onboarding(USER, {"servings": "2", "cooking_time": "30"}.get(current, "x"))


def sent_markup(context, call=-1):
    return context.bot.send_message.call_args_list[call].kwargs.get("reply_markup")


def callbacks(markup):
    return [b.callback_data for row in markup.inline_keyboard for b in row]


async def test_servings_callback_saves_and_asks_time(database):
    await advance_to("servings")
    update, query = make_callback("onb:servings:3")
    context = make_context()

    await handlers.handle_onboarding_callback(update, context)

    assert (await load_profile(USER))["servings"] == "3"
    edited = query.edit_message_text.call_args.args[0]
    assert edited.startswith("Вопрос") and "✓ 3 порции" in edited
    assert "onb:time:30" in callbacks(sent_markup(context))
    query.answer.assert_awaited()


async def test_time_callback_shows_equipment_keyboard_and_resets_state(database):
    await advance_to("cooking_time")
    update, query = make_callback("onb:time:60")
    context = make_context({"onb_equipment": {3}, "onb_custom": ["старое"]})

    await handlers.handle_onboarding_callback(update, context)

    assert (await load_profile(USER))["cooking_time"] == "60"
    assert "✓ до 60 минут" in query.edit_message_text.call_args.args[0]
    markup = sent_markup(context)
    assert "onb:eq:done" in callbacks(markup)
    assert not any(b.text.startswith("✅") for row in markup.inline_keyboard for b in row)
    assert context.user_data["onb_equipment"] == set()
    assert context.user_data["onb_custom"] == []
    assert context.user_data["onb_msg"] == 100


async def test_stale_callback_writes_nothing_and_clears_keyboard(database):
    await advance_to("cooking_time")
    update, query = make_callback("onb:servings:7")
    context = make_context()

    await handlers.handle_onboarding_callback(update, context)

    query.answer.assert_awaited_once_with("Этот вопрос уже неактуален")
    query.edit_message_reply_markup.assert_awaited_once_with(reply_markup=None)
    context.bot.send_message.assert_not_awaited()
    profile = await load_profile(USER)
    assert profile["servings"] == "2"
    assert profile["onboarding_step"] == 5


async def test_double_tap_is_stale(database):
    await advance_to("servings")
    context = make_context()
    first, _ = make_callback("onb:servings:3")
    await handlers.handle_onboarding_callback(first, context)
    second, query = make_callback("onb:servings:7")
    await handlers.handle_onboarding_callback(second, context)

    query.answer.assert_awaited_once_with("Этот вопрос уже неактуален")
    assert (await load_profile(USER))["servings"] == "3"


async def test_callback_from_unapproved_user_is_ignored(database):
    update, query = make_callback("onb:servings:3", user_id=STRANGER)
    context = make_context()

    await handlers.handle_onboarding_callback(update, context)

    query.answer.assert_awaited_once_with()
    query.edit_message_text.assert_not_awaited()
    context.bot.send_message.assert_not_awaited()


async def test_edit_failure_still_sends_next_step(database):
    await advance_to("servings")
    update, query = make_callback("onb:servings:3")
    query.edit_message_text.side_effect = BadRequest("message to edit not found")
    context = make_context()

    await handlers.handle_onboarding_callback(update, context)

    assert (await load_profile(USER))["servings"] == "3"
    assert "onb:time:30" in callbacks(sent_markup(context))


async def test_equipment_toggle_updates_state_and_keyboard(database):
    await advance_to("equipment")
    context = make_context(fresh_equipment_state())
    update, query = make_callback("onb:eq:0")
    await handlers.handle_onboarding_callback(update, context)

    assert context.user_data["onb_equipment"] == {0}
    markup = query.edit_message_reply_markup.call_args.kwargs["reply_markup"]
    assert markup.inline_keyboard[0][0].text == f"✅ {EQUIPMENT_OPTIONS[0]}"

    update, query = make_callback("onb:eq:0")
    await handlers.handle_onboarding_callback(update, context)
    assert context.user_data["onb_equipment"] == set()


async def test_equipment_toggle_with_bad_index_is_ignored(database):
    await advance_to("equipment")
    context = make_context(fresh_equipment_state())
    update, query = make_callback("onb:eq:999")
    await handlers.handle_onboarding_callback(update, context)
    assert context.user_data.get("onb_equipment", set()) == set()
    query.edit_message_reply_markup.assert_not_awaited()


async def test_equipment_other_prompts_and_remembers_message(database):
    await advance_to("equipment")
    context = make_context(fresh_equipment_state())
    update, query = make_callback("onb:eq:other", message_id=55)

    await handlers.handle_onboarding_callback(update, context)

    assert context.user_data["onb_msg"] == 55
    assert "через запятую" in context.bot.send_message.call_args.kwargs["text"]


async def test_equipment_text_adds_custom_and_edits_keyboard_message(database):
    await advance_to("equipment")
    context = make_context({"onb_msg": 55})

    await handlers.handle_message(make_text("Казан, вакууматор, духовка"), context)

    assert context.user_data["onb_custom"] == ["казан", "вакууматор"]
    assert context.user_data["onb_equipment"] == {EQUIPMENT_OPTIONS.index("духовка")}
    edit = context.bot.edit_message_text.call_args.kwargs
    assert edit["message_id"] == 55
    assert "Добавлено: казан, вакууматор" in edit["text"]
    profile = await load_profile(USER)
    assert profile["onboarding_step"] == 6 and not profile["onboarding_done"]
    assert profile["equipment"] == []


async def test_equipment_text_without_keyboard_message_sends_new_one(database):
    await advance_to("equipment")
    context = make_context()

    await handlers.handle_message(make_text("казан"), context)

    context.bot.edit_message_text.assert_not_awaited()
    assert "onb:eq:done" in callbacks(sent_markup(context))
    assert context.user_data["onb_msg"] == 100


async def test_equipment_done_saves_selected_and_custom_and_finishes(database):
    await advance_to("equipment")
    context = make_context({"onb_equipment": {0, 5}, "onb_custom": ["казан"], "onb_msg": 7})
    update, query = make_callback("onb:eq:done", text="Какая техника?")

    await handlers.handle_onboarding_callback(update, context)

    profile = await load_profile(USER)
    assert profile["onboarding_done"] is True
    assert sorted(profile["equipment"]) == sorted([EQUIPMENT_OPTIONS[0], EQUIPMENT_OPTIONS[5], "казан"])
    assert "✓" in query.edit_message_text.call_args.args[0]
    assert "всё запомнил" in context.bot.send_message.call_args.kwargs["text"]
    assert sent_markup(context) is None
    assert "onb_equipment" not in context.user_data


async def test_equipment_done_with_nothing_selected(database):
    await advance_to("equipment")
    context = make_context(fresh_equipment_state())
    update, query = make_callback("onb:eq:done")

    await handlers.handle_onboarding_callback(update, context)

    profile = await load_profile(USER)
    assert profile["onboarding_done"] is True and profile["equipment"] == []
    assert "ничего из списка" in query.edit_message_text.call_args.args[0]


async def test_invalid_text_on_choice_step_repeats_keyboard(database):
    await advance_to("cooking_time")
    context = make_context()

    await handlers.handle_message(make_text("минут 40"), context)

    assert "кнопк" in context.bot.send_message.call_args.kwargs["text"]
    assert "onb:time:15" in callbacks(sent_markup(context))
    assert (await load_profile(USER))["onboarding_step"] == 5


async def test_valid_text_on_choice_step_moves_on(database):
    await advance_to("servings")
    context = make_context()

    await handlers.handle_message(make_text("на 4"), context)

    assert (await load_profile(USER))["servings"] == "4"
    assert "onb:time:30" in callbacks(sent_markup(context))


async def test_text_step_has_no_keyboard(database):
    await run_onboarding(USER, "")
    context = make_context()

    await handlers.handle_message(make_text("итальянская"), context)

    assert sent_markup(context) is None


async def test_start_mid_equipment_resets_selection(database):
    await advance_to("equipment")
    context = make_context({"onb_equipment": {1}, "onb_custom": ["казан"], "onb_msg": 3})

    await handlers.start(make_text("/start"), context)

    markup = sent_markup(context)
    assert not any(b.text.startswith("✅") for row in markup.inline_keyboard for b in row)
    assert context.user_data["onb_equipment"] == set()
    assert context.user_data["onb_custom"] == []


async def test_start_for_new_onboarding_shows_first_question(database):
    context = make_context()

    await handlers.start(make_text("/start"), context)

    assert "Какие кухни" in context.bot.send_message.call_args.kwargs["text"]
    assert sent_markup(context) is None


async def test_callback_after_finish_is_stale(database):
    await advance_to("equipment")
    await apply_onboarding_choice(USER, "equipment", ["духовка"])
    update, query = make_callback("onb:eq:done")

    await handlers.handle_onboarding_callback(update, make_context())

    query.answer.assert_awaited_once_with("Этот вопрос уже неактуален")
    assert (await load_profile(USER))["equipment"] == ["духовка"]


@pytest.mark.parametrize("data", ["onb:eq:done", "onb:eq:2", "onb:eq:other"])
async def test_equipment_callback_after_state_loss_restarts_step(database, data):
    # бот перезапустился: на экране старые галочки, а user_data пуст — не сохраняем «ничего»
    await advance_to("equipment")
    context = make_context()
    update, query = make_callback(data)

    await handlers.handle_onboarding_callback(update, context)

    profile = await load_profile(USER)
    assert not profile["onboarding_done"] and profile["equipment"] == []
    assert "onb:eq:done" in callbacks(sent_markup(context))
    assert context.user_data["onb_equipment"] == set()
    query.answer.assert_awaited_once()
    assert "заново" in query.answer.call_args.args[0]
    query.edit_message_reply_markup.assert_awaited_once_with(reply_markup=None)


async def test_equipment_text_with_nothing_new_still_answers(database):
    await advance_to("equipment")
    context = make_context({"onb_equipment": {0}, "onb_custom": [], "onb_msg": 55})
    context.bot.edit_message_text.side_effect = BadRequest("Message is not modified")

    await handlers.handle_message(make_text("духовка"), context)

    assert "уже отмечено" in context.bot.send_message.call_args.kwargs["text"]


async def test_new_equipment_keyboard_disables_the_previous_one(database):
    await advance_to("equipment")
    context = make_context({"onb_equipment": {1}, "onb_custom": [], "onb_msg": 3})

    await handlers.start(make_text("/start"), context)

    context.bot.edit_message_reply_markup.assert_awaited_once_with(
        chat_id=USER, message_id=3, reply_markup=None
    )
    assert context.user_data["onb_msg"] == 100


async def test_equipment_options_order_is_stable_contract():
    # callback_data хранит индекс: перестановка списка перепутала бы кнопки уже отправленных сообщений
    assert EQUIPMENT_OPTIONS[:3] == ["духовка", "плита", "микроволновка"]

