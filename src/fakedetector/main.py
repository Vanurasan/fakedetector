"""Точка входа приложения."""

import argparse
import sys
from collections.abc import Sequence

import uvicorn

from fakedetector.app import create_app
from fakedetector.config.loader import ConfigurationError, load_config


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

    app = create_app(config)
    uvicorn.run(app, host=config.server.host, port=config.server.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
