"""Точка входа приложения."""

import argparse
import sys
from collections.abc import Sequence

import uvicorn

from fakedetector.app import create_app
from fakedetector.config.loader import ConfigurationError, load_config
from fakedetector.logging_setup import configure_logging


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Запустить FakeDetector")
    parser.add_argument(
        "--config",
        default="config/config.example.yaml",
        help="путь к YAML-файлу конфигурации",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Загрузить конфигурацию и запустить приложение."""
    args = _parse_args(argv)

    try:
        config = load_config(args.config)
    except ConfigurationError:
        print(
            "Configuration error: unable to load or validate configuration.",
            file=sys.stderr,
        )
        return 2

    logger = configure_logging(config.logging)
    app = create_app(config)
    logger.info(
        "Application is starting.",
        extra={
            "event": "application_starting",
            "schema_version": config.schema_version,
            "host": config.server.host,
            "port": config.server.port,
        },
    )
    uvicorn.run(app, host=config.server.host, port=config.server.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
