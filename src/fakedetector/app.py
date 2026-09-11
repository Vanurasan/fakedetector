"""Модуль создания приложения FastAPI."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from fakedetector._runtime import _build_production_runtime
from fakedetector.api import install_api
from fakedetector.auth import load_api_authenticator, load_webui_authenticator
from fakedetector.config.models import AppConfig
from fakedetector.lifecycle import SchedulerStateError
from fakedetector.webui import install_webui


def create_app(config: AppConfig) -> FastAPI:
    """Создать и настроить экземпляр FastAPI-приложения."""
    api_authenticator = load_api_authenticator(config.access_channels.api)
    webui_authenticator = load_webui_authenticator(config.access_channels.webui)
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
    app.state.application_service = runtime.application_service

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    if config.access_channels.api.enabled:
        install_api(
            app,
            service=runtime.application_service,
            authenticator=api_authenticator,
        )
    if config.access_channels.webui.enabled:
        install_webui(
            app,
            service=runtime.application_service,
            authenticator=webui_authenticator,
            config=config,
        )

    return app
