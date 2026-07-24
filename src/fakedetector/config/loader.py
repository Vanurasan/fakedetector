"""YAML configuration loader with Pydantic validation."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError as PydanticValidationError

from fakedetector.config.models import AppConfig


class ConfigurationError(Exception):
    """Controlled error raised when configuration cannot be loaded or validated.

    The message is safe for logging and does not expose secrets or internal paths.
    """


def load_config(config_path: str | Path) -> AppConfig:
    """Load and validate application configuration from a YAML file.

    Args:
        config_path: Explicit path to the YAML configuration file.

    Returns:
        A fully validated and typed AppConfig instance.

    Raises:
        ConfigurationError: If the file is missing, YAML is malformed,
            or the data fails Pydantic validation.
    """
    path = Path(config_path)

    if not path.is_file():
        raise ConfigurationError("Configuration file not found")

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError:
        raise ConfigurationError("Cannot read configuration file") from None

    try:
        raw_data = yaml.safe_load(raw_text)
    except yaml.YAMLError:
        raise ConfigurationError("Configuration file contains invalid YAML") from None

    if raw_data is None:
        raw_data = {}

    if not isinstance(raw_data, dict):
        raise ConfigurationError("Configuration must be a YAML mapping")

    try:
        config = AppConfig.model_validate(raw_data)
    except PydanticValidationError:
        raise ConfigurationError("Configuration validation failed") from None

    return config
