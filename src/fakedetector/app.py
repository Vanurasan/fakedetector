"""Модуль создания приложения FastAPI."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from fakedetector._runtime import _build_production_runtime
from fakedetector.config.models import AppConfig


def create_app(config: AppConfig) -> FastAPI:
    """Создать и настроить экземпляр FastAPI-приложения."""
    runtime = _build_production_runtime(config)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        runtime.scheduler.start()
        try:
            yield
        finally:
            runtime.scheduler.shutdown()

    app = FastAPI(title="FakeDetector", version="0.1.0", lifespan=lifespan)
    app.state.config = config
    app.state.runtime = runtime

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
