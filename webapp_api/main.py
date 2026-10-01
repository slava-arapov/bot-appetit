from fastapi import FastAPI

from webapp_api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="Bot Appetit Mini App API")
    app.include_router(router)
    return app
