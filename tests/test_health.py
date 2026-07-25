"""Тесты health endpoint."""

from fastapi.testclient import TestClient

from fakedetector.app import create_app
from fakedetector.config.models import AppConfig


def make_config() -> AppConfig:
    """Создать минимальную валидную конфигурацию для тестов."""
    return AppConfig.model_validate(
        {
            "schema_version": "1.0",
            "server": {},
            "access_channels": {},
            "limits": {},
            "allowed_formats": {},
            "validation": {},
            "temporary_storage": {},
            "preprocessing": {},
            "analyzers": {},
            "risk_assessment": {},
            "result": {},
            "error_handling": {},
            "logging": {},
            "external_systems": {},
        }
    )


def test_health_returns_200() -> None:
    """GET /health возвращает HTTP 200."""
    app = create_app(make_config())
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_ok_body() -> None:
    """GET /health возвращает точное тело {"status": "ok"}."""
    app = create_app(make_config())
    client = TestClient(app)
    response = client.get("/health")
    assert response.json() == {"status": "ok"}


def test_create_app_stores_config() -> None:
    """Фабрика сохраняет переданную конфигурацию в состоянии приложения."""
    config = make_config()

    app = create_app(config)

    assert app.state.config is config
