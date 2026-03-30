from telegramify_markdown import markdownify

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from agent.chef import run_agent, run_onboarding
from config import ADMIN_USER_ID
from memory.store import load_profile


async def _send(update: Update, text: str):
    try:
        await update.message.reply_text(markdownify(text), parse_mode=ParseMode.MARKDOWN_V2)
    except BadRequest:
        await update.message.reply_text(text)


async def _is_admin(update: Update) -> bool:
    return update.effective_user.id == ADMIN_USER_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update):
        return
    profile = load_profile()
    if not profile.get("onboarding_done"):
        reply = await run_onboarding("")
    else:
        reply = "Привет! Я снова здесь. Что приготовим?"
    await _send(update, reply)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update):
        return
    user_text = update.message.text
    profile = load_profile()

    if not profile.get("onboarding_done"):
        reply = await run_onboarding(user_text)
        model_name = None
    else:
        reply, model_name = await run_agent(user_text)

    if model_name:
        reply = f"{reply}\n\n_{model_name}_"

    await _send(update, reply)