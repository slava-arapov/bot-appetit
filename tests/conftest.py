import os

# config.py читает обязательные переменные при импорте
os.environ.setdefault("TELEGRAM_TOKEN", "123456:TEST-TOKEN")
os.environ.setdefault("OPENROUTER_API_KEY", "test")
os.environ.setdefault("ADMIN_USER_ID", "1")

import httpx
import pytest_asyncio

import memory.db as db
from webapp_api.main import create_app


@pytest_asyncio.fixture
async def database(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    await db.init_db()
    yield db.get_conn()
    await db.close_db()


@pytest_asyncio.fixture
async def client(database):
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
