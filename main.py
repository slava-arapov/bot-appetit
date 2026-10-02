import datetime
import logging

from telegram import BotCommand, BotCommandScopeChat, MenuButtonWebApp, WebAppInfo
from telegram.error import TelegramError
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from config import ADMIN_USER_ID, API_HOST, API_PORT, TELEGRAM_TOKEN, WEBAPP_URL
from bot.handlers import (
    start,
    handle_message,
    handle_approval_callback,
    handle_reset_callback,
    handle_onboarding_callback,
    error_handler,
    pending_command,
    broadcast_command,
    stats_command,
    cook_command,
    random_command,
    pantry_command,
    profile_command,
    reset_command,
)
from bot.jobs import notify_expiring
from memory.db import init_db, close_db
from memory.stats import record_command
from webapp_api.server import start_api, stop_api

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

DEFAULT_COMMANDS = [
    BotCommand("start", "Начать / забыть последние сообщения"),
    BotCommand("cook", "Что приготовить из того, что есть"),
    BotCommand("random", "Случайное блюдо-сюрприз"),
    BotCommand("pantry", "Мои запасы"),
    BotCommand("profile", "Моя анкета"),
    BotCommand("reset", "Сбросить память бота"),
]

ADMIN_COMMANDS = DEFAULT_COMMANDS + [
    BotCommand("pending", "Заявки на одобрение"),
    BotCommand("broadcast", "Разослать сообщение всем пользователям"),
    BotCommand("stats", "Статистика вызовов команд"),
]


MENU_BUTTON_TEXT = "Кухня"


async def _set_menu_button(bot, url: str):
    """Ставит кнопку меню, открывающую Mini App. Пустой url — кнопку не трогаем.

    Telegram принимает для Mini App только https-адрес. Ошибка Telegram не должна ронять бота:
    он и без кнопки работает, а причина видна в логе.
    """
    url = url.strip()
    if not url:
        return
    if not url.startswith("https://"):
        logging.warning("WEBAPP_URL должен начинаться с https:// — кнопка меню не установлена: %r", url)
        return
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text=MENU_BUTTON_TEXT, web_app=WebAppInfo(url=url))
        )
    except TelegramError:
        logging.exception("Не удалось установить кнопку меню Mini App (%s)", url)


def _tracked(name: str, handler):
    """Оборачивает командный хендлер, инкрементируя счётчик вызовов в data/stats.json."""
    async def wrapper(update, context):
        await record_command(name)
        await handler(update, context)
    return wrapper


async def _post_init(app: Application):
    await init_db()
    app.bot_data["api"] = await start_api(API_HOST, API_PORT)
    await app.bot.set_my_commands(DEFAULT_COMMANDS)
    await app.bot.set_my_commands(
        ADMIN_COMMANDS,
        scope=BotCommandScopeChat(chat_id=ADMIN_USER_ID),
    )
    await _set_menu_button(app.bot, WEBAPP_URL)


async def _post_shutdown(app: Application):
    api = app.bot_data.pop("api", None)
    if api:
        await stop_api(*api)
    await close_db()


def main():
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    app.add_handler(CommandHandler("start", _tracked("start", start)))
    app.add_handler(CommandHandler("cook", _tracked("cook", cook_command)))
    app.add_handler(CommandHandler("random", _tracked("random", random_command)))
    app.add_handler(CommandHandler("pantry", _tracked("pantry", pantry_command)))
    app.add_handler(CommandHandler("profile", _tracked("profile", profile_command)))
    app.add_handler(CommandHandler("reset", _tracked("reset", reset_command)))
    app.add_handler(CommandHandler("pending", _tracked("pending", pending_command)))
    app.add_handler(CommandHandler("broadcast", _tracked("broadcast", broadcast_command)))
    app.add_handler(CommandHandler("stats", _tracked("stats", stats_command)))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_approval_callback, pattern=r"^(approve|reject):"))
    app.add_handler(CallbackQueryHandler(handle_reset_callback, pattern=r"^reset"))
    app.add_handler(CallbackQueryHandler(handle_onboarding_callback, pattern=r"^onb:"))
    app.add_error_handler(error_handler)
    app.job_queue.run_daily(notify_expiring, time=datetime.time(9, 0))
    logging.info("Bot Appetit запущен")
    app.run_polling()


if __name__ == "__main__":
    main()
