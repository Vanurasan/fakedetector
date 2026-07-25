"""Модуль создания приложения FastAPI."""

from fastapi import FastAPI

from fakedetector.config.models import AppConfig


def create_app(config: AppConfig) -> FastAPI:
    """Создать и настроить экземпляр FastAPI-приложения."""
    app = FastAPI(title="FakeDetector", version="0.1.0")
    app.state.config = config

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
