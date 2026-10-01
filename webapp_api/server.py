import asyncio
import contextlib

import uvicorn

from webapp_api.main import create_app


class _EmbeddedServer(uvicorn.Server):
    """uvicorn внутри чужого event loop: сигналами (Ctrl+C, остановка) управляет PTB, не uvicorn."""

    @contextlib.contextmanager
    def capture_signals(self):
        yield


async def _serve(server: _EmbeddedServer) -> None:
    try:
        await server.serve()
    except SystemExit as e:
        # uvicorn делает sys.exit(1) при ошибке старта (например, порт занят);
        # внутри asyncio-задачи это убило бы весь цикл
        raise RuntimeError(f"uvicorn завершился при старте (код {e.code})") from None


async def start_api(host: str, port: int) -> tuple[uvicorn.Server, asyncio.Task]:
    """Запускает API в текущем event loop; бросает RuntimeError, если не удалось подняться."""
    config = uvicorn.Config(create_app(), host=host, port=port, log_level="info")
    server = _EmbeddedServer(config)
    task = asyncio.create_task(_serve(server))
    while not server.started:
        if task.done():
            task.result()  # пробрасывает RuntimeError
            raise RuntimeError("API-сервер остановился при старте")
        await asyncio.sleep(0.05)
    return server, task


async def stop_api(server: uvicorn.Server, task: asyncio.Task) -> None:
    server.should_exit = True
    await task
