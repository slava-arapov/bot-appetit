from unittest.mock import AsyncMock

import pytest
from telegram import MenuButtonWebApp
from telegram.error import BadRequest, NetworkError

import main

URL = "https://botappetit.goida.root.sx"


def make_bot():
    return AsyncMock()


async def test_sets_web_app_menu_button():
    bot = make_bot()

    await main._set_menu_button(bot, URL)

    bot.set_chat_menu_button.assert_awaited_once()
    button = bot.set_chat_menu_button.call_args.kwargs["menu_button"]
    assert isinstance(button, MenuButtonWebApp)
    assert button.text == main.MENU_BUTTON_TEXT
    assert button.web_app.url == URL


@pytest.mark.parametrize("url", ["", "   ", "http://botappetit.goida.root.sx", "botappetit.goida.root.sx"])
async def test_skips_when_url_is_empty_or_not_https(url, caplog):
    bot = make_bot()

    await main._set_menu_button(bot, url)

    bot.set_chat_menu_button.assert_not_awaited()
    if url.strip():  # заданный, но негодный адрес — это ошибка конфигурации, о ней надо сказать в логе
        assert "WEBAPP_URL" in caplog.text


@pytest.mark.parametrize("error", [BadRequest("Wrong URL"), NetworkError("timeout")])
async def test_telegram_error_does_not_stop_startup(error, caplog):
    bot = make_bot()
    bot.set_chat_menu_button.side_effect = error

    await main._set_menu_button(bot, URL)  # не должно бросать

    assert "кнопк" in caplog.text.lower()


async def test_post_init_sets_button_from_config(monkeypatch):
    monkeypatch.setattr(main, "WEBAPP_URL", URL)
    monkeypatch.setattr(main, "init_db", AsyncMock())
    monkeypatch.setattr(main, "start_api", AsyncMock(return_value=("server", "task")))
    app = AsyncMock()
    app.bot_data = {}

    await main._post_init(app)

    button = app.bot.set_chat_menu_button.call_args.kwargs["menu_button"]
    assert button.web_app.url == URL
