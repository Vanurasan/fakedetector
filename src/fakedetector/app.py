"""Модуль создания приложения FastAPI."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from fakedetector._runtime import _build_production_runtime
from fakedetector.config.models import AppConfig
from fakedetector.lifecycle import SchedulerStateError


def create_app(config: AppConfig) -> FastAPI:
    """Создать и настроить экземпляр FastAPI-приложения."""
    runtime = _build_production_runtime(config)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        startup_completed = False
        try:
            runtime.scheduler.start()
            startup_completed = True
            yield
        except BaseException:
            if startup_completed or not runtime.scheduler.is_stopped:
                try:
                    runtime.scheduler.shutdown()
                except SchedulerStateError:
                    if startup_completed:
                        raise
                except BaseException:
                    # shutdown() reports worker termination after joining workers
                    # and reaching STOPPED. Only that completed cleanup may defer
                    # to the active caller exception; unfinished shutdown must fail.
                    if not runtime.scheduler.is_stopped:
                        raise
            raise
        else:
            runtime.scheduler.shutdown()

    app = FastAPI(title="FakeDetector", version="0.1.0", lifespan=lifespan)
    app.state.config = config
    app.state.runtime = runtime

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
