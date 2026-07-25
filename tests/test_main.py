"""Тесты точки запуска приложения."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI

from fakedetector import main as main_module
from fakedetector.config.loader import ConfigurationError
from fakedetector.config.models import AppConfig


def make_config(*, host: str = "127.0.0.1", port: int = 8080) -> AppConfig:
    """Создать минимальную валидную конфигурацию для тестов."""
    return AppConfig.model_validate(
        {
            "schema_version": "1.0",
            "server": {"host": host, "port": port},
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


def test_main_loads_default_config_and_runs_uvicorn(monkeypatch) -> None:
    """main загружает путь по умолчанию и запускает Uvicorn с настройками."""
    config = make_config(host="0.0.0.0", port=9090)
    loaded_paths: list[str | Path] = []
    uvicorn_calls: list[tuple[FastAPI, str, int]] = []

    def fake_load_config(config_path: str | Path) -> AppConfig:
        loaded_paths.append(config_path)
        return config

    def fake_uvicorn_run(app: FastAPI, *, host: str, port: int) -> None:
        uvicorn_calls.append((app, host, port))

    monkeypatch.setattr(main_module, "load_config", fake_load_config)
    monkeypatch.setattr(main_module.uvicorn, "run", fake_uvicorn_run)

    result = main_module.main([])

    assert result == 0
    assert loaded_paths == ["config/config.example.yaml"]
    assert len(uvicorn_calls) == 1
    app, host, port = uvicorn_calls[0]
    assert app.state.config is config
    assert (host, port) == ("0.0.0.0", 9090)


def test_config_argument_is_passed_to_loader(monkeypatch) -> None:
    """--config передаёт выбранный путь в загрузчик."""
    config = make_config()
    loaded_paths: list[str | Path] = []

    def fake_load_config(config_path: str | Path) -> AppConfig:
        loaded_paths.append(config_path)
        return config

    monkeypatch.setattr(main_module, "load_config", fake_load_config)
    monkeypatch.setattr(main_module.uvicorn, "run", lambda *args, **kwargs: None)

    result = main_module.main(["--config", "custom/settings.yaml"])

    assert result == 0
    assert loaded_paths == ["custom/settings.yaml"]


def test_configuration_error_is_safe_and_skips_uvicorn(
    monkeypatch,
    capsys,
) -> None:
    """Ошибка конфигурации безопасна и не запускает сервер."""
    secret = "super-secret-token"
    uvicorn_called = False

    def fake_load_config(config_path: str | Path) -> AppConfig:
        raise ConfigurationError(f"invalid secret: {secret}")

    def fake_uvicorn_run(*args, **kwargs) -> None:
        nonlocal uvicorn_called
        uvicorn_called = True

    monkeypatch.setattr(main_module, "load_config", fake_load_config)
    monkeypatch.setattr(main_module.uvicorn, "run", fake_uvicorn_run)

    result = main_module.main(["--config", "broken.yaml"])
    captured = capsys.readouterr()

    assert result == 2
    assert not uvicorn_called
    assert "Configuration error" in captured.err
    assert secret not in captured.err


def test_non_utf8_config_returns_error_without_running_uvicorn(capsys, monkeypatch) -> None:
    """A real malformed UTF-8 config fails safely before Uvicorn starts."""
    config_bytes = b"\xff\xfe\x00"
    uvicorn_calls: list[tuple[object, ...]] = []
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as config_file:
        config_file.write(config_bytes)
        config_path = Path(config_file.name)

    try:
        def fake_uvicorn_run(*args: object, **kwargs: object) -> None:
            uvicorn_calls.append(args)

        monkeypatch.setattr(main_module.uvicorn, "run", fake_uvicorn_run)

        result = main_module.main(["--config", str(config_path)])
        captured = capsys.readouterr()

        assert result == 2
        assert uvicorn_calls == []
        assert str(config_path) not in captured.err
        assert repr(config_bytes) not in captured.err
        assert config_bytes.decode("latin-1") not in captured.err
    finally:
        config_path.unlink(missing_ok=True)
