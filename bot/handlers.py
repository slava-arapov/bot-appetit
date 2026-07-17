import asyncio
import logging

from telegramify_markdown import markdownify

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes
from telegram.error import BadRequest, Forbidden, TimedOut

from agent.chef import run_agent, run_onboarding, current_onboarding_question
from config import ADMIN_USER_ID
from memory.store import (
    load_profile,
    load_pantry,
    reset_context,
    reset_onboarding,
    reset_all,
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


def _resolve_access(update: Update) -> str:
    user_id = update.effective_user.id
    if user_id == ADMIN_USER_ID:
        ensure_approved(user_id, update.effective_user.username)
        return "approved"
    status = get_user_status(user_id)
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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    access = _resolve_access(update)
    user_id = update.effective_user.id

    if access == "new":
        register_pending(user_id, update.effective_user.username)
        await _notify_admin_new_request(update, context)
        await _send(update, "Заявка отправлена, жди одобрения 👀")
        return
    if access == "pending":
        await _send(update, "Заявка ещё не одобрена, подожди немного 👀")
        return
    if access == "rejected":
        if not is_rejection_notified(user_id):
            mark_rejection_notified(user_id)
            await _send(update, "Доступ отклонён.")
        return

    profile = load_profile(user_id)
    if not profile.get("onboarding_done"):
        reply = await _show_onboarding_question(update, context, user_id)
    else:
        reset_context(user_id)
        reply = "Привет! Начинаем с чистого листа — что приготовим?"
    await _send(update, reply)


async def _require_approved(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Обрабатывает new/pending/rejected сама, возвращает True только для approved."""
    access = _resolve_access(update)
    user_id = update.effective_user.id

    if access == "approved":
        return True
    if access == "new":
        register_pending(user_id, update.effective_user.username)
        await _notify_admin_new_request(update, context)
        await _send(update, "Заявка отправлена, жди одобрения 👀")
    elif access == "rejected":
        if not is_rejection_notified(user_id):
            mark_rejection_notified(user_id)
            await _send(update, "Доступ отклонён.")
    # pending: молчим, чтобы не спамить повторными заявками
    return False


async def _show_onboarding_question(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> str:
    """Показывает текущий вопрос анкеты, не отвечая на него автоматически."""
    if load_profile(user_id).get("onboarding_step", 0) == 0:
        return await _with_typing(update, context, run_onboarding(user_id, ""))
    return current_onboarding_question(user_id)


async def _require_onboarded(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Как _require_approved, но дополнительно требует законченный онбординг.

    Нужна для команд-шорткатов (/cook, /random, ...), которые шлют агенту заготовленный
    текст: если анкета не закончена, такой текст иначе попал бы в run_onboarding() как
    "ответ" на текущий вопрос и затёр бы его.
    """
    if not await _require_approved(update, context):
        return False

    user_id = update.effective_user.id
    if load_profile(user_id).get("onboarding_done"):
        return True

    question = await _show_onboarding_question(update, context, user_id)
    await _send(update, f"Давай сначала закончим анкету 📋\n\n{question}")
    return False


async def _run_agent_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str):
    user_id = update.effective_user.id
    profile = load_profile(user_id)

    if not profile.get("onboarding_done"):
        reply = await _with_typing(update, context, run_onboarding(user_id, user_text))
        model_name = None
    else:
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


_PANTRY_STATUS_LABELS = {"have": "✅ Есть", "low": "⚠️ Мало", "out": "❌ Нет"}


def _format_pantry_list(pantry: list[dict]) -> str:
    if not pantry:
        return "Запасы пусты."

    groups: dict[str, list[dict]] = {"have": [], "low": [], "out": []}
    for item in pantry:
        groups.setdefault(item.get("status", "have"), []).append(item)

    lines = []
    for status in ("have", "low", "out"):
        items = groups.get(status, [])
        if not items:
            continue
        lines.append(f"{_PANTRY_STATUS_LABELS.get(status, status)}:")
        for item in items:
            quantity = f", {item['quantity']}" if item.get("quantity") else ""
            expiry = f", годен до {item['expiry_date']}" if item.get("expiry_date") else ""
            lines.append(f"- {item['name']}{quantity}{expiry}")
        lines.append("")

    return "\n".join(lines).strip()


async def pantry_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_onboarded(update, context):
        return
    pantry = load_pantry(update.effective_user.id)
    await _send(update, _format_pantry_list(pantry))


def _format_profile(profile: dict) -> str:
    def joined(field):
        return ", ".join(profile.get(field, [])) or "не указано"

    lines = [
        f"😋 Любит: {joined('likes')}",
        f"🚫 Не любит: {joined('dislikes')}",
        f"⛔ Ограничения: {joined('restrictions')}",
        f"🍳 Техника и посуда: {joined('equipment')}",
    ]
    if profile.get("servings"):
        lines.append(f"👥 Обычно готовит на: {profile['servings']}")
    if profile.get("cooking_time"):
        lines.append(f"⏱ Время на готовку: {profile['cooking_time']}")
    return "\n".join(lines)


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_onboarded(update, context):
        return
    profile = load_profile(update.effective_user.id)
    await _send(update, _format_profile(profile))


def _do_reset_chat(user_id: int) -> str:
    reset_context(user_id)
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
            reset_fn(user_id)
            await query.edit_message_text(text)
            question = await run_onboarding(user_id, "")
            await _send_to_chat(context, query.message.chat_id, question)
        else:
            handler = _RESET_ACTIONS.get(action)
            if handler:
                await query.edit_message_text(handler(user_id))
        await query.answer()
        return

    warning = _DANGEROUS_RESET_ACTIONS.get(action)
    if warning:
        await query.edit_message_text(warning, reply_markup=_confirm_keyboard(action))
    else:
        handler = _RESET_ACTIONS.get(action)
        if handler:
            await query.edit_message_text(handler(query.from_user.id))
    await query.answer()


async def handle_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_USER_ID:
        await query.answer()
        return

    action, target_id_str = query.data.split(":")
    target_id = int(target_id_str)

    if action == "approve":
        approve_user(target_id)
        await query.edit_message_text(query.message.text + "\n\n✅ Одобрено")
        await context.bot.send_message(chat_id=target_id, text="Доступ открыт! Погнали 🍳")

        profile = load_profile(target_id)
        if not profile.get("onboarding_done"):
            reply = await run_onboarding(target_id, "")
            try:
                await context.bot.send_message(
                    chat_id=target_id, text=markdownify(reply), parse_mode=ParseMode.MARKDOWN_V2
                )
            except BadRequest:
                await context.bot.send_message(chat_id=target_id, text=reply)
    else:
        reject_user(target_id)
        mark_rejection_notified(target_id)
        await query.edit_message_text(query.message.text + "\n\n❌ Отклонено")
        await context.bot.send_message(chat_id=target_id, text="Доступ отклонён.")

    await query.answer()


async def pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        return

    pending = list_pending_users()
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

    counts = count_users_by_status()
    lines = [
        "👥 Пользователи:",
        f"- одобрены: {counts['approved']}",
        f"- ожидают: {counts['pending']}",
        f"- отклонены: {counts['rejected']}",
        "",
        "📊 Команды:",
    ]

    stats = get_stats()
    if stats:
        lines += [f"- /{name}: {count}" for name, count in sorted(stats.items(), key=lambda kv: kv[1], reverse=True)]
    else:
        lines.append("- пока нет вызовов")

    await _send(update, "\n".join(lines))


async def _send_to_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str) -> bool:
    try:
        await context.bot.send_message(chat_id=chat_id, text=markdownify(text), parse_mode=ParseMode.MARKDOWN_V2)
        return True
    except BadRequest:
        try:
            await context.bot.send_message(chat_id=chat_id, text=text)
            return True
        except (BadRequest, Forbidden, TimedOut):
            return False
    except (Forbidden, TimedOut):
        return False


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
    for user_id in list_approved_user_ids():
        if await _send_preformatted_to_chat(context, user_id, mv2_text, plain_text):
            sent += 1
        else:
            failed += 1

    await _send(update, f"Разослано: {sent}, не доставлено: {failed}")
