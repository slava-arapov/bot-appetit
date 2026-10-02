import asyncio
import logging

from telegramify_markdown import markdownify

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes
from telegram.error import BadRequest, Forbidden, TimedOut

from agent.chef import (
    ONBOARDING_STEPS,
    StepView,
    apply_onboarding_choice,
    current_onboarding_question,
    run_agent,
    run_onboarding,
    split_items,
)
from bot.keyboards import equipment_keyboard, keyboard_for
from config import ADMIN_USER_ID, EQUIPMENT_OPTIONS
from memory.store import (
    load_profile,
    reset_context,
    reset_onboarding,
    reset_all,
    describe_servings,
    describe_cooking_time,
    normalize_tag,
)
from memory.users import (
    get_user_status,
    register_pending,
    approve_user,
    reject_user,
    mark_rejection_notified,
    is_rejection_notified,
    list_approved_user_ids,
    list_pending_users,
    ensure_approved,
    count_users_by_status,
)
from memory.stats import get_stats

logger = logging.getLogger(__name__)

TYPING_REFRESH_SECONDS = 4
_MAX_SEND_RETRIES = 3

COOK_PROMPT = "Предложи рецепт из того, что есть дома прямо сейчас — используй только продукты из моих запасов (pantry), без похода в магазин."
RANDOM_PROMPT = "Удиви меня — предложи случайное блюдо-сюрприз с учётом моих вкусов и ограничений."


async def _send(update: Update, text: str):
    for attempt in range(_MAX_SEND_RETRIES):
        try:
            await update.message.reply_text(markdownify(text), parse_mode=ParseMode.MARKDOWN_V2)
            return
        except BadRequest:
            await update.message.reply_text(text)
            return
        except TimedOut:
            if attempt < _MAX_SEND_RETRIES - 1:
                await asyncio.sleep(2)
            else:
                logger.error("Не удалось отправить сообщение после %d попыток (TimedOut)", _MAX_SEND_RETRIES)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Необработанное исключение", exc_info=context.error)


async def _resolve_access(update: Update) -> str:
    user_id = update.effective_user.id
    if user_id == ADMIN_USER_ID:
        await ensure_approved(user_id, update.effective_user.username)
        return "approved"
    status = await get_user_status(user_id)
    return status or "new"


async def _notify_admin_new_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.username and f"@{user.username}" or user.full_name
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Одобрить", callback_data=f"approve:{user.id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject:{user.id}"),
    ]])
    await context.bot.send_message(
        chat_id=ADMIN_USER_ID,
        text=f"Новая заявка на доступ: {name} (id {user.id})",
        reply_markup=keyboard,
    )


async def _with_typing(update: Update, context: ContextTypes.DEFAULT_TYPE, coro):
    """Показывает "печатает..." в чате, пока выполняется coro (статус Telegram держится ~5с, поэтому обновляем его периодически)."""
    chat_id = update.effective_chat.id
    stop = asyncio.Event()

    async def keep_typing():
        while not stop.is_set():
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            try:
                await asyncio.wait_for(stop.wait(), timeout=TYPING_REFRESH_SECONDS)
            except asyncio.TimeoutError:
                pass

    typing_task = asyncio.create_task(keep_typing())
    try:
        return await coro
    finally:
        stop.set()
        await typing_task


async def _send_message(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, reply_markup=None
) -> Message | None:
    """Шлёт сообщение в MarkdownV2 (при BadRequest — обычным текстом). None — не доставлено."""
    try:
        return await context.bot.send_message(
            chat_id=chat_id, text=markdownify(text), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=reply_markup
        )
    except BadRequest:
        try:
            return await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
        except (BadRequest, Forbidden, TimedOut):
            return None
    except (Forbidden, TimedOut):
        return None


# Состояние шага «техника» живёт в context.user_data (в БД пишется только итог по «Готово»):
# onb_equipment — индексы выбранных пунктов EQUIPMENT_OPTIONS, onb_custom — свои пункты,
# onb_msg — id сообщения с клавиатурой, которое перерисовывается при добавлении своих пунктов.
_ONB_STATE_KEYS = ("onb_equipment", "onb_custom", "onb_msg")
_STALE_ANSWER = "Этот вопрос уже неактуален"


def _reset_onboarding_state(context: ContextTypes.DEFAULT_TYPE):
    for key in _ONB_STATE_KEYS:
        context.user_data.pop(key, None)


async def _send_view(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, view: StepView, *, fresh: bool = True
) -> Message | None:
    """Показывает шаг анкеты с его клавиатурой. fresh=True на шаге техники начинает выбор с нуля."""
    step = view.step
    is_equipment = step is not None and step.kind == "multiselect"
    previous_msg = context.user_data.get("onb_msg") if fresh and is_equipment else None
    if fresh and is_equipment:
        _reset_onboarding_state(context)
        context.user_data["onb_equipment"] = set()
        context.user_data["onb_custom"] = []
    markup = keyboard_for(step, context.user_data.get("onb_equipment"))
    message = await _send_message(context, chat_id, view.text, markup)
    if message is not None and is_equipment:
        context.user_data["onb_msg"] = message.message_id
        if previous_msg is not None and previous_msg != message.message_id:
            # кнопки старого сообщения иначе остались бы живыми и показывали бы устаревшие галочки
            try:
                await context.bot.edit_message_reply_markup(chat_id=chat_id, message_id=previous_msg, reply_markup=None)
            except (BadRequest, Forbidden, TimedOut):
                pass
    return message


async def _is_approved(user_id: int) -> bool:
    return user_id == ADMIN_USER_ID or await get_user_status(user_id) == "approved"


async def _active_onboarding_field(user_id: int) -> str | None:
    """Поле шага, ждущего ответа; None — анкета не начата или закончена."""
    profile = await load_profile(user_id)
    step_number = profile.get("onboarding_step", 0)
    if profile.get("onboarding_done") or step_number == 0:
        return None
    return ONBOARDING_STEPS[step_number - 1].field


async def _answer_stale(query):
    await query.answer(_STALE_ANSWER)
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except BadRequest:
        pass


async def _mark_answered(query, answer: str):
    """Дописывает выбранное к вопросу и убирает клавиатуру. Не удалось — не страшно, шаг уже сохранён."""
    try:
        await query.edit_message_text(f"{query.message.text}\n\n✓ {answer}")
    except BadRequest:
        pass


def _choice_label(field: str, value: str) -> str:
    describe = describe_servings if field == "servings" else describe_cooking_time
    return describe(value) or value


def _equipment_text(custom: list[str]) -> str:
    step = next(s for s in ONBOARDING_STEPS if s.kind == "multiselect")
    return f"{step.question}\n\nДобавлено: {', '.join(custom)}" if custom else step.question


async def handle_onboarding_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if not await _is_approved(user_id):
        await query.answer()
        return

    _, kind, value = query.data.split(":", 2)
    field = {"servings": "servings", "time": "cooking_time", "eq": "equipment"}.get(kind)
    if field is None or field != await _active_onboarding_field(user_id):
        await _answer_stale(query)
        return

    if kind == "eq":
        await _handle_equipment_callback(query, context, user_id, value)
        return

    view = await apply_onboarding_choice(user_id, field, value)
    if view is None:
        await _answer_stale(query)
        return
    await query.answer()
    if view.step is not None and view.step.field == field:
        return  # значение не прошло проверку, шаг остался на месте
    await _mark_answered(query, _choice_label(field, value))
    await _send_view(context, query.message.chat_id, view)


async def _handle_equipment_callback(query, context: ContextTypes.DEFAULT_TYPE, user_id: int, value: str):
    selected: set[int] | None = context.user_data.get("onb_equipment")
    if selected is None:
        # состояние потеряно (рестарт бота), а на экране остались старые галочки: не гадаем, что было
        # отмечено, и не сохраняем пустой список по «Готово» — начинаем выбор заново
        await query.answer("Выбор сбросился, отметь технику заново")
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except BadRequest:
            pass
        await _send_view(context, query.message.chat_id, await current_onboarding_question(user_id))
        return
    custom: list[str] = context.user_data.setdefault("onb_custom", [])

    if value == "other":
        context.user_data["onb_msg"] = query.message.message_id
        await query.answer()
        await _send_message(context, query.message.chat_id, "Напиши через запятую, чего не хватает в списке ✏️")
        return

    if value == "done":
        items = [EQUIPMENT_OPTIONS[i] for i in sorted(selected)] + custom
        view = await apply_onboarding_choice(user_id, "equipment", items)
        if view is None:
            await _answer_stale(query)
            return
        await query.answer()
        _reset_onboarding_state(context)
        await _mark_answered(query, ", ".join(items) or "ничего из списка")
        await _send_view(context, query.message.chat_id, view)
        return

    if not value.isdigit() or int(value) >= len(EQUIPMENT_OPTIONS):
        await query.answer()
        return
    selected.symmetric_difference_update({int(value)})
    await query.answer()
    try:
        await query.edit_message_reply_markup(reply_markup=equipment_keyboard(selected))
    except BadRequest:
        pass


async def _add_custom_equipment(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Текст на шаге техники — это «своя» техника: пункты из списка отмечаются, остальные добавляются."""
    selected: set[int] = context.user_data.setdefault("onb_equipment", set())
    custom: list[str] = context.user_data.setdefault("onb_custom", [])
    for item in split_items(text):
        name = normalize_tag(item)
        if name in EQUIPMENT_OPTIONS:
            selected.add(EQUIPMENT_OPTIONS.index(name))
        elif name not in custom:
            custom.append(name)

    chat_id = update.effective_chat.id
    markup = equipment_keyboard(selected)
    message_id = context.user_data.get("onb_msg")
    if message_id is not None:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=message_id, text=_equipment_text(custom), reply_markup=markup
            )
            await _send_message(context, chat_id, "Добавил 👍 Жми «Готово», когда закончишь.")
            return
        except BadRequest as e:
            if "not modified" in str(e).lower():
                await _send_message(context, chat_id, "Это уже отмечено 👍")
                return
    message = await _send_message(context, chat_id, _equipment_text(custom), markup)
    if message is not None:
        context.user_data["onb_msg"] = message.message_id


async def _handle_onboarding_text(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    field = await _active_onboarding_field(user_id)
    step = next((s for s in ONBOARDING_STEPS if s.field == field), None)
    if step is not None and step.kind == "multiselect":
        await _add_custom_equipment(update, context, text)
        return
    view = await _with_typing(update, context, run_onboarding(user_id, text))
    await _send_view(context, update.effective_chat.id, view)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    access = await _resolve_access(update)
    user_id = update.effective_user.id

    if access == "new":
        await register_pending(user_id, update.effective_user.username)
        await _notify_admin_new_request(update, context)
        await _send(update, "Заявка отправлена, жди одобрения 👀")
        return
    if access == "pending":
        await _send(update, "Заявка ещё не одобрена, подожди немного 👀")
        return
    if access == "rejected":
        if not await is_rejection_notified(user_id):
            await mark_rejection_notified(user_id)
            await _send(update, "Доступ отклонён.")
        return

    profile = await load_profile(user_id)
    if not profile.get("onboarding_done"):
        view = await _show_onboarding_question(update, context, user_id)
        await _send_view(context, update.effective_chat.id, view)
    else:
        await reset_context(user_id)
        await _send(update, "Привет! Начинаем с чистого листа — что приготовим?")


async def _require_approved(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Обрабатывает new/pending/rejected сама, возвращает True только для approved."""
    access = await _resolve_access(update)
    user_id = update.effective_user.id

    if access == "approved":
        return True
    if access == "new":
        await register_pending(user_id, update.effective_user.username)
        await _notify_admin_new_request(update, context)
        await _send(update, "Заявка отправлена, жди одобрения 👀")
    elif access == "rejected" and not await is_rejection_notified(user_id):
        await mark_rejection_notified(user_id)
        await _send(update, "Доступ отклонён.")
    # pending: молчим, чтобы не спамить повторными заявками
    return False


async def _show_onboarding_question(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> StepView:
    """Показывает текущий вопрос анкеты, не отвечая на него автоматически."""
    profile = await load_profile(user_id)
    if profile.get("onboarding_step", 0) == 0:
        return await _with_typing(update, context, run_onboarding(user_id, ""))
    return await current_onboarding_question(user_id)


async def _require_onboarded(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Как _require_approved, но дополнительно требует законченный онбординг.

    Нужна для команд-шорткатов (/cook, /random, ...), которые шлют агенту заготовленный
    текст: если анкета не закончена, такой текст иначе попал бы в run_onboarding() как
    "ответ" на текущий вопрос и затёр бы его.
    """
    if not await _require_approved(update, context):
        return False

    user_id = update.effective_user.id
    profile = await load_profile(user_id)
    if profile.get("onboarding_done"):
        return True

    view = await _show_onboarding_question(update, context, user_id)
    await _send_view(context, update.effective_chat.id, StepView(f"Давай сначала закончим анкету 📋\n\n{view.text}", view.step))
    return False


async def _run_agent_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str):
    user_id = update.effective_user.id
    profile = await load_profile(user_id)

    if not profile.get("onboarding_done"):
        await _handle_onboarding_text(update, context, user_id, user_text)
        return

    reply, model_name = await _with_typing(update, context, run_agent(user_id, user_text))

    if model_name:
        reply = f"{reply}\n\n||_{model_name}_||"

    await _send(update, reply)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_approved(update, context):
        return
    await _run_agent_reply(update, context, update.message.text)


async def cook_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_onboarded(update, context):
        return
    await _run_agent_reply(update, context, COOK_PROMPT)


async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_onboarded(update, context):
        return
    await _run_agent_reply(update, context, RANDOM_PROMPT)


async def _do_reset_chat(user_id: int) -> str:
    await reset_context(user_id)
    return "Переписка забыта, начинаем с чистого листа 🧹"


_RESET_ACTIONS = {
    "chat": _do_reset_chat,
}

_DANGEROUS_RESET_ACTIONS = {
    "onboarding": (
        "Точно заполнить анкету заново? Текущие вкусы, ограничения и техника "
        "будут перезаписаны по ходу вопросов."
    ),
    "all": "Точно забыть всё — анкету, историю, запасы и переписку? Это нельзя отменить.",
}

# После этих действий анкета обнулена — сразу же перезапускаем онбординг.
_RESTART_ONBOARDING_ACTIONS = {
    "onboarding": (reset_onboarding, "Хорошо, заполняем анкету заново 📋"),
    "all": (reset_all, "Забыл всё, что знал о тебе. Начинаем с начала 🔄"),
}

RESET_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🗑 Забыть последние сообщения", callback_data="reset:chat")],
    [InlineKeyboardButton("📋 Заполнить анкету заново", callback_data="reset:onboarding")],
    [InlineKeyboardButton("⚠️ Забыть всё и начать с начала", callback_data="reset:all")],
])


def _confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Да", callback_data=f"reset_confirm:{action}"),
        InlineKeyboardButton("Нет", callback_data="reset_cancel"),
    ]])


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_approved(update, context):
        return
    await update.message.reply_text("Что сбросить?", reply_markup=RESET_KEYBOARD)


async def handle_reset_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "reset_cancel":
        await query.edit_message_text("Отменено.")
        await query.answer()
        return

    action = data.split(":", 1)[1]

    if data.startswith("reset_confirm:"):
        user_id = query.from_user.id
        restart = _RESTART_ONBOARDING_ACTIONS.get(action)
        if restart:
            reset_fn, text = restart
            await reset_fn(user_id)
            await query.edit_message_text(text)
            _reset_onboarding_state(context)
            await _send_view(context, query.message.chat_id, await run_onboarding(user_id, ""))
        else:
            handler = _RESET_ACTIONS.get(action)
            if handler:
                await query.edit_message_text(await handler(user_id))
        await query.answer()
        return

    warning = _DANGEROUS_RESET_ACTIONS.get(action)
    if warning:
        await query.edit_message_text(warning, reply_markup=_confirm_keyboard(action))
    else:
        handler = _RESET_ACTIONS.get(action)
        if handler:
            await query.edit_message_text(await handler(query.from_user.id))
    await query.answer()


async def handle_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_USER_ID:
        await query.answer()
        return

    action, target_id_str = query.data.split(":")
    target_id = int(target_id_str)

    if action == "approve":
        await approve_user(target_id)
        await query.edit_message_text(query.message.text + "\n\n✅ Одобрено")
        await context.bot.send_message(chat_id=target_id, text="Доступ открыт! Погнали 🍳")

        profile = await load_profile(target_id)
        if not profile.get("onboarding_done"):
            await _send_view(context, target_id, await run_onboarding(target_id, ""))
    else:
        await reject_user(target_id)
        await mark_rejection_notified(target_id)
        await query.edit_message_text(query.message.text + "\n\n❌ Отклонено")
        await context.bot.send_message(chat_id=target_id, text="Доступ отклонён.")

    await query.answer()


async def pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        return

    pending = await list_pending_users()
    if not pending:
        await _send(update, "Нет заявок на одобрение.")
        return

    for entry in pending:
        name = f"@{entry['username']}" if entry.get("username") else str(entry["user_id"])
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve:{entry['user_id']}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject:{entry['user_id']}"),
        ]])
        await update.message.reply_text(
            f"{name} (id {entry['user_id']}), заявка от {entry.get('requested_at', '?')}",
            reply_markup=keyboard,
        )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        return

    counts = await count_users_by_status()
    lines = [
        "👥 Пользователи:",
        f"- одобрены: {counts['approved']}",
        f"- ожидают: {counts['pending']}",
        f"- отклонены: {counts['rejected']}",
        "",
        "📊 Команды:",
    ]

    stats = await get_stats()
    if stats:
        lines += [f"- /{name}: {count}" for name, count in sorted(stats.items(), key=lambda kv: kv[1], reverse=True)]
    else:
        lines.append("- пока нет вызовов")

    await _send(update, "\n".join(lines))


async def _send_to_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str) -> bool:
    return await _send_message(context, chat_id, text) is not None


async def _send_preformatted_to_chat(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, mv2_text: str, plain_text: str
) -> bool:
    try:
        await context.bot.send_message(chat_id=chat_id, text=mv2_text, parse_mode=ParseMode.MARKDOWN_V2)
        return True
    except BadRequest:
        try:
            await context.bot.send_message(chat_id=chat_id, text=plain_text)
            return True
        except (BadRequest, Forbidden, TimedOut):
            return False
    except (Forbidden, TimedOut):
        return False


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        return

    plain_parts = update.message.text.split(maxsplit=1)
    if len(plain_parts) < 2:
        await _send(update, "Использование: /broadcast <текст>")
        return

    plain_text = plain_parts[1]
    # text_markdown_v2 реконструирует MarkdownV2-разметку из entities сообщения:
    # клиент Telegram при наборе сам превращает **жирный** в entity и стирает
    # звёздочки из update.message.text, так что форматирование иначе теряется.
    mv2_parts = (update.message.text_markdown_v2 or plain_text).split(maxsplit=1)
    mv2_text = mv2_parts[1] if len(mv2_parts) > 1 else plain_text

    sent, failed = 0, 0
    for user_id in await list_approved_user_ids():
        if await _send_preformatted_to_chat(context, user_id, mv2_text, plain_text):
            sent += 1
        else:
            failed += 1

    await _send(update, f"Разослано: {sent}, не доставлено: {failed}")
