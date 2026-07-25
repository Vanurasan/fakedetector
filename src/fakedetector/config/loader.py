"""YAML configuration loader with Pydantic validation and env var override."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import yaml
from pydantic import ValidationError as PydanticValidationError

from fakedetector.config.models import AppConfig

_ENV_PREFIX = "FAKEDETECTOR_"
_NESTED_SEPARATOR = "__"


class ConfigurationError(Exception):
    """Controlled error raised when configuration cannot be loaded or validated.

    The message is safe for logging and does not expose secrets or internal paths.
    """


def _parse_env_value(raw: str) -> object:
    """Parse an environment variable string into a typed value.

    Uses YAML safe_load so that ``"8080"`` becomes an integer,
    ``"true"``/``"false"`` become booleans, ``"[1,2,3]"`` becomes a list,
    and bare strings remain strings.
    """
    try:
        value = yaml.safe_load(raw)
    except yaml.YAMLError:
        # If it doesn't look like YAML, keep it as a string.
        return raw
    # yaml.safe_load on a plain scalar returns the Python type; but for
    # a dict/list it also works.  We intentionally allow nested structures
    # so that list settings (e.g. allowed extensions) can be replaced.
    return value


def _apply_env_overrides(
    raw_data: dict[str, object],
    *,
    env: Mapping[str, str],
) -> dict[str, object]:
    """Apply ``FAKEDETECTOR_*`` environment variables on top of *raw_data*.

    Rules
    -----
    * Only variables whose name starts with ``FAKEDETECTOR_`` are processed.
    * The rest of the name is split on ``__`` (double underscore) to form
      a dotted path into the configuration tree.
    * The value is parsed through ``yaml.safe_load`` so that strings,
      integers, booleans and list literals are converted correctly.
    * If the resulting dotted path does not map to a valid configuration
      field, Pydantic validation will later reject it (``extra="forbid"``).
    """
    import copy

    result = copy.deepcopy(raw_data)

    for key, str_value in env.items():
        if not key.startswith(_ENV_PREFIX):
            continue

        suffix = key[len(_ENV_PREFIX):]
        if not suffix:
            raise ConfigurationError(
                f"Environment variable {key} has an invalid configuration path"
            )

        parts = suffix.split(_NESTED_SEPARATOR)
        if any(not part for part in parts):
            raise ConfigurationError(
                f"Environment variable {key} has an invalid configuration path"
            )
        parts = [part.lower() for part in parts]

        parse_error = False
        try:
            parsed = _parse_env_value(str_value)
        except Exception:
            parse_error = True

        if parse_error:
            raise ConfigurationError(
                f"Environment variable {key} has an unparseable value"
            )

        # Walk / create the nested dict structure.
        cursor: dict[str, object] = result
        for part in parts[:-1]:
            if part not in cursor or not isinstance(cursor[part], dict):
                cursor[part] = {}
            cursor = cast("dict[str, object]", cursor[part])

        cursor[parts[-1]] = parsed

    return result


def load_config(
    config_path: str | Path,
    env: Mapping[str, str] | None = None,
) -> AppConfig:
    """Load and validate application configuration from a YAML file,
    optionally overriding settings with environment variables.

    Args:
        config_path: Explicit path to the YAML configuration file.
        env: Optional mapping of environment variables (name → value).
            When ``None`` (default), ``os.environ`` is used.  A
            caller-provided mapping enables deterministic testing.

    Returns:
        A fully validated and typed :class:`AppConfig` instance.

    Raises:
        ConfigurationError: If the file is missing, YAML is malformed,
            env-var overlay produces an unknown path, or the data fails
            Pydantic validation.  Error messages never expose raw
            environment variable values.
    """
    path = Path(config_path)

    if not path.is_file():
        raise ConfigurationError("Configuration file not found")

    read_error: str | None = None
    raw_text: str | None = None
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError:
        read_error = "Cannot read configuration file"
    except UnicodeError:
        read_error = "Configuration file is not valid UTF-8"

    if read_error is not None:
        raise ConfigurationError(read_error)

    assert raw_text is not None
    yaml_error = False
    try:
        raw_data = yaml.safe_load(raw_text)
    except yaml.YAMLError:
        yaml_error = True

    if yaml_error:
        raise ConfigurationError("Configuration file contains invalid YAML")

    if raw_data is None:
        raw_data = {}

    if not isinstance(raw_data, dict):
        raise ConfigurationError("Configuration must be a YAML mapping")

    # ---- env-var override ----
    if env is None:
        env = os.environ

    overridden = _apply_env_overrides(raw_data, env=env)

    validation_error = False
    try:
        config = AppConfig.model_validate(overridden)
    except PydanticValidationError:
        validation_error = True

    if validation_error:
        # Build a safe message that mentions *which* env var is problematic
        # but never includes its value.
        env_var_names = sorted(
            k for k in env if k.startswith(_ENV_PREFIX)
        )
        if env_var_names:
            detail = (
                "Configuration validation failed after applying "
                "environment variable(s): "
                + ", ".join(env_var_names)
            )
        else:
            detail = "Configuration validation failed"
        raise ConfigurationError(detail)

    return config
