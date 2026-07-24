"""Тесты health endpoint."""

from fastapi.testclient import TestClient

from fakedetector.app import create_app


def test_health_returns_200() -> None:
    """GET /health возвращает HTTP 200."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_ok_body() -> None:
    """GET /health возвращает точное тело {"status": "ok"}."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/health")
    assert response.json() == {"status": "ok"}
