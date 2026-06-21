import logging
from datetime import date

from telegramify_markdown import markdownify
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from config import ADMIN_USER_ID
from memory.store import check_expiring_soon

logger = logging.getLogger(__name__)


def _format_date(iso_date: str) -> str:
    return date.fromisoformat(iso_date).strftime("%d.%m")


async def notify_expiring(context: ContextTypes.DEFAULT_TYPE):
    expiring = check_expiring_soon()
    if not expiring:
        return

    lines = [f"- {item['name']} (до {_format_date(item['expiry_date'])})" for item in expiring]
    text = "⏰ Скоро испортится:\n" + "\n".join(lines)

    try:
        await context.bot.send_message(
            chat_id=ADMIN_USER_ID, text=markdownify(text), parse_mode=ParseMode.MARKDOWN_V2
        )
    except BadRequest:
        await context.bot.send_message(chat_id=ADMIN_USER_ID, text=text)
