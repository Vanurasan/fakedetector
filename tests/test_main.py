"""Тесты точки запуска приложения."""

from __future__ import annotations

import logging
import tempfile
from io import StringIO
from pathlib import Path

import yaml
from fastapi import FastAPI

from fakedetector import main as main_module
from fakedetector.config.loader import ConfigurationError
from fakedetector.config.models import AppConfig
from fakedetector.logging_setup import LoggingSetupError
from fakedetector.runtime_setup import RuntimeSetupError


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
    events: list[object] = []

    class FakeLogger:
        def info(self, message: str, *, extra: dict[str, object]) -> None:
            events.append(("log", message, extra))

    def fake_configure_logging(logging_config) -> logging.Logger:
        events.append(("configure", logging_config))
        return FakeLogger()  # type: ignore[return-value]

    def fake_runtime_setup(runtime_config: AppConfig) -> None:
        events.append(("runtime", runtime_config))

    def fake_create_app(app_config: AppConfig) -> FastAPI:
        events.append(("create_app", app_config))
        app = FastAPI()
        app.state.config = app_config
        return app

    def fake_load_config(config_path: str | Path) -> AppConfig:
        loaded_paths.append(config_path)
        events.append(("load", config_path))
        return config

    def fake_uvicorn_run(app: FastAPI, *, host: str, port: int) -> None:
        events.append(("uvicorn", host, port))
        uvicorn_calls.append((app, host, port))

    monkeypatch.setattr(main_module, "load_config", fake_load_config)
    monkeypatch.setattr(main_module, "ensure_runtime_directories", fake_runtime_setup)
    monkeypatch.setattr(main_module, "configure_logging", fake_configure_logging)
    monkeypatch.setattr(main_module, "create_app", fake_create_app)
    monkeypatch.setattr(main_module.uvicorn, "run", fake_uvicorn_run)

    result = main_module.main([])

    assert result == 0
    assert loaded_paths == ["config/config.example.yaml"]
    assert len(uvicorn_calls) == 1
    app, host, port = uvicorn_calls[0]
    assert app.state.config is config
    assert (host, port) == ("0.0.0.0", 9090)
    assert events[0] == ("load", "config/config.example.yaml")
    assert events[1] == ("runtime", config)
    assert events[2] == ("configure", config.logging)
    assert events[3] == ("create_app", config)
    assert events[4] == (
        "log",
        "Application is starting.",
        {
            "event": "application_starting",
            "schema_version": "1.0",
            "host": "0.0.0.0",
            "port": 9090,
        },
    )
    assert events[5] == ("uvicorn", "0.0.0.0", 9090)
    assert sum(event[0] == "runtime" for event in events) == 1


def test_config_argument_is_passed_to_loader(monkeypatch) -> None:
    """--config передаёт выбранный путь в загрузчик."""
    config = make_config()
    loaded_paths: list[str | Path] = []
    log_extras: list[dict[str, object]] = []

    class FakeLogger:
        def info(self, message: str, *, extra: dict[str, object]) -> None:
            log_extras.append(extra)

    def fake_load_config(config_path: str | Path) -> AppConfig:
        loaded_paths.append(config_path)
        return config

    monkeypatch.setattr(main_module, "load_config", fake_load_config)
    monkeypatch.setattr(main_module, "ensure_runtime_directories", lambda config: None)
    monkeypatch.setattr(
        main_module,
        "configure_logging",
        lambda config: FakeLogger(),
    )
    monkeypatch.setattr(main_module.uvicorn, "run", lambda *args, **kwargs: None)

    result = main_module.main(["--config", "custom/settings.yaml"])

    assert result == 0
    assert loaded_paths == ["custom/settings.yaml"]
    assert log_extras == [
        {
            "event": "application_starting",
            "schema_version": "1.0",
            "host": "127.0.0.1",
            "port": 8080,
        }
    ]
    assert "custom/settings.yaml" not in repr(log_extras)


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
    monkeypatch.setattr(
        main_module,
        "ensure_runtime_directories",
        lambda config: (_ for _ in ()).throw(AssertionError("runtime setup after error")),
    )
    monkeypatch.setattr(
        main_module,
        "configure_logging",
        lambda config: (_ for _ in ()).throw(AssertionError("logging configured after error")),
    )
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
        monkeypatch.setattr(
            main_module,
            "ensure_runtime_directories",
            lambda config: (_ for _ in ()).throw(AssertionError("runtime setup after error")),
        )
        monkeypatch.setattr(
            main_module,
            "configure_logging",
            lambda config: (_ for _ in ()).throw(AssertionError("logging configured after error")),
        )

        result = main_module.main(["--config", str(config_path)])
        captured = capsys.readouterr()

        assert result == 2
        assert uvicorn_calls == []
        assert str(config_path) not in captured.err
        assert repr(config_bytes) not in captured.err
        assert config_bytes.decode("latin-1") not in captured.err
    finally:
        config_path.unlink(missing_ok=True)


def test_runtime_setup_error_is_safe_and_stops_startup(monkeypatch, capsys) -> None:
    """Runtime initialization failure exits safely before logging and app creation."""
    config = make_config()
    sentinel = "secret-like-sentinel"
    unsafe_path = f"runtime/{sentinel}/logs"
    runtime_calls: list[AppConfig] = []

    def fail_runtime_setup(runtime_config: AppConfig) -> None:
        runtime_calls.append(runtime_config)
        raise RuntimeSetupError(f"cannot create {unsafe_path}: {sentinel}")

    monkeypatch.setattr(main_module, "load_config", lambda path: config)
    monkeypatch.setattr(main_module, "ensure_runtime_directories", fail_runtime_setup)
    monkeypatch.setattr(
        main_module,
        "configure_logging",
        lambda logging_config: (_ for _ in ()).throw(
            AssertionError("logging configured after runtime error")
        ),
    )
    monkeypatch.setattr(
        main_module,
        "create_app",
        lambda app_config: (_ for _ in ()).throw(
            AssertionError("application created after runtime error")
        ),
    )
    monkeypatch.setattr(
        main_module.uvicorn,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Uvicorn started after runtime error")
        ),
    )

    result = main_module.main([])
    captured = capsys.readouterr()

    assert result == 3
    assert runtime_calls == [config]
    assert "Runtime initialization failed" in captured.err
    assert unsafe_path not in captured.err
    assert sentinel not in captured.err


def test_logging_setup_error_is_safe_and_stops_startup(monkeypatch, capsys) -> None:
    config = make_config()
    unsafe_detail = "unsafe-system-detail"
    calls: list[str] = []

    def fail_logging_setup(logging_config) -> logging.Logger:
        calls.append("configure_logging")
        error = LoggingSetupError()
        error.args = (f"unsafe path: {unsafe_detail}",)
        raise error

    monkeypatch.setattr(main_module, "load_config", lambda path: config)
    monkeypatch.setattr(main_module, "ensure_runtime_directories", lambda config: None)
    monkeypatch.setattr(main_module, "configure_logging", fail_logging_setup)
    monkeypatch.setattr(
        main_module,
        "create_app",
        lambda config: (_ for _ in ()).throw(AssertionError("application created")),
    )
    monkeypatch.setattr(
        main_module.uvicorn,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Uvicorn started")),
    )

    result = main_module.main([])
    captured = capsys.readouterr()

    assert result == 4
    assert calls == ["configure_logging"]
    assert captured.out == ""
    assert captured.err == "Logging initialization failed.\n"
    assert unsafe_detail not in captured.err


def test_unsupported_yaml_logging_level_exits_before_uvicorn(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    unsupported_level = "unsafe-cli-level"
    config_data = yaml.safe_load(
        Path("config/config.example.yaml").read_text(encoding="utf-8")
    )
    config_data["logging"]["level"] = unsupported_level
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")

    monkeypatch.setattr(
        main_module,
        "ensure_runtime_directories",
        lambda config: (_ for _ in ()).throw(AssertionError("runtime setup")),
    )
    monkeypatch.setattr(
        main_module,
        "create_app",
        lambda config: (_ for _ in ()).throw(AssertionError("application created")),
    )
    monkeypatch.setattr(
        main_module.uvicorn,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Uvicorn started")),
    )

    result = main_module.main(["--config", str(config_path)])
    captured = capsys.readouterr()

    assert result == 2
    assert captured.out == ""
    assert captured.err == (
        "Configuration error: unable to load or validate configuration.\n"
    )
    assert unsupported_level not in captured.err


def test_yaml_directory_log_target_exits_safely_before_application_start(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    config_data = yaml.safe_load(
        Path("config/config.example.yaml").read_text(encoding="utf-8")
    )
    log_target = tmp_path / "existing-directory"
    log_target.mkdir()
    config_data["logging"]["jsonl_path"] = str(log_target)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")

    logger = logging.getLogger("fakedetector")
    foreign_stream = StringIO()
    foreign_handler = logging.StreamHandler(foreign_stream)
    logger.addHandler(foreign_handler)
    try:
        monkeypatch.setattr(
            main_module,
            "create_app",
            lambda config: (_ for _ in ()).throw(AssertionError("application created")),
        )
        monkeypatch.setattr(
            main_module.uvicorn,
            "run",
            lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Uvicorn started")),
        )

        result = main_module.main(["--config", str(config_path)])
        captured = capsys.readouterr()

        assert result == 4
        assert captured.out == ""
        assert captured.err == "Logging initialization failed.\n"
        assert str(log_target) not in captured.err
        assert foreign_stream.getvalue() == ""
    finally:
        logger.removeHandler(foreign_handler)
        foreign_handler.close()
