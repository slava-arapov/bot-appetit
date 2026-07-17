import datetime
import logging

from telegram import BotCommand, BotCommandScopeChat
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from config import ADMIN_USER_ID, TELEGRAM_TOKEN
from bot.handlers import (
    start,
    handle_message,
    handle_approval_callback,
    error_handler,
    pending_command,
    broadcast_command,
)
from bot.jobs import notify_expiring

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


async def _post_init(app: Application):
    await app.bot.set_my_commands([
        BotCommand("start", "Начать / перезапустить"),
    ])
    await app.bot.set_my_commands(
        [
            BotCommand("start", "Начать / перезапустить"),
            BotCommand("pending", "Заявки на одобрение"),
            BotCommand("broadcast", "Разослать сообщение всем пользователям"),
        ],
        scope=BotCommandScopeChat(chat_id=ADMIN_USER_ID),
    )


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(_post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pending", pending_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_approval_callback))
    app.add_error_handler(error_handler)
    app.job_queue.run_daily(notify_expiring, time=datetime.time(9, 0))
    logging.info("Bot Appetit запущен")
    app.run_polling()


if __name__ == "__main__":
    main()
