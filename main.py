import datetime
import logging

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from config import TELEGRAM_TOKEN
from bot.handlers import start, handle_message
from bot.jobs import notify_expiring

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.job_queue.run_daily(notify_expiring, time=datetime.time(9, 0))
    logging.info("Bot Appetit запущен")
    app.run_polling()


if __name__ == "__main__":
    main()
