import socket

import httpx
import pytest

from webapp_api.server import start_api, stop_api


async def test_start_serves_requests_and_stops(database):
    server, task = await start_api("127.0.0.1", 0)
    try:
        port = server.servers[0].sockets[0].getsockname()[1]
        async with httpx.AsyncClient() as c:
            r = await c.get(f"http://127.0.0.1:{port}/api/me")
        assert r.status_code == 401
    finally:
        await stop_api(server, task)
    assert task.done()


async def test_busy_port_raises():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        port = s.getsockname()[1]
        with pytest.raises(RuntimeError):
            await start_api("127.0.0.1", port)
