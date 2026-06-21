import asyncio

from telegramify_markdown import markdownify

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from agent.chef import run_agent, run_onboarding
from config import ADMIN_USER_ID
from memory.store import load_profile
from memory.users import (
    get_user_status,
    register_pending,
    approve_user,
    reject_user,
    mark_rejection_notified,
    is_rejection_notified,
)

TYPING_REFRESH_SECONDS = 4


async def _send(update: Update, text: str):
    try:
        await update.message.reply_text(markdownify(text), parse_mode=ParseMode.MARKDOWN_V2)
    except BadRequest:
        await update.message.reply_text(text)


def _resolve_access(update: Update) -> str:
    user_id = update.effective_user.id
    if user_id == ADMIN_USER_ID:
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
        reply = await _with_typing(update, context, run_onboarding(user_id, ""))
    else:
        reply = "Привет! Я снова здесь. Что приготовим?"
    await _send(update, reply)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    access = _resolve_access(update)
    user_id = update.effective_user.id

    if access == "new":
        register_pending(user_id, update.effective_user.username)
        await _notify_admin_new_request(update, context)
        await _send(update, "Заявка отправлена, жди одобрения 👀")
        return
    if access == "pending":
        return
    if access == "rejected":
        if not is_rejection_notified(user_id):
            mark_rejection_notified(user_id)
            await _send(update, "Доступ отклонён.")
        return

    user_text = update.message.text
    profile = load_profile(user_id)

    if not profile.get("onboarding_done"):
        reply = await _with_typing(update, context, run_onboarding(user_id, user_text))
        model_name = None
    else:
        reply, model_name = await _with_typing(update, context, run_agent(user_id, user_text))

    if model_name:
        reply = f"{reply}\n\n||_{model_name}_||"

    await _send(update, reply)


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
    else:
        reject_user(target_id)
        mark_rejection_notified(target_id)
        await query.edit_message_text(query.message.text + "\n\n❌ Отклонено")
        await context.bot.send_message(chat_id=target_id, text="Доступ отклонён.")

    await query.answer()
