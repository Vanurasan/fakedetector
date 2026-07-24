"""Модуль создания приложения FastAPI."""

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Создать и настроить экземпляр FastAPI-приложения."""
    app = FastAPI(title="FakeDetector", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
