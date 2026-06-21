import logging
from datetime import date

from telegramify_markdown import markdownify
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from memory.store import check_expiring_soon
from memory.users import list_approved_user_ids

logger = logging.getLogger(__name__)


def _format_date(iso_date: str) -> str:
    return date.fromisoformat(iso_date).strftime("%d.%m")


async def notify_expiring(context: ContextTypes.DEFAULT_TYPE):
    for user_id in list_approved_user_ids():
        expiring = check_expiring_soon(user_id)
        if not expiring:
            continue

        lines = [f"- {item['name']} (до {_format_date(item['expiry_date'])})" for item in expiring]
        text = "⏰ Скоро испортится:\n" + "\n".join(lines)

        try:
            await context.bot.send_message(
                chat_id=user_id, text=markdownify(text), parse_mode=ParseMode.MARKDOWN_V2
            )
        except BadRequest:
            await context.bot.send_message(chat_id=user_id, text=text)
