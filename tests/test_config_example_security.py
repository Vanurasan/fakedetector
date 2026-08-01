"""Security guard for the canonical example configuration."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_EXAMPLE_CONFIG_PATH = Path("config/config.example.yaml")
_SECRET_FIELD_NAMES = {
    "token",
    "api_token",
    "access_token",
    "refresh_token",
    "password",
    "passphrase",
    "secret",
    "client_secret",
    "api_key",
    "private_key",
    "secret_key",
}
_ENV_VAR_NAME_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def _find_literal_secret_fields(value: object, path: str = "root") -> list[str]:
    """Return paths whose exact field name denotes a literal secret value."""
    findings: list[str] = []

    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if (
                isinstance(key, str)
                and key.casefold() in _SECRET_FIELD_NAMES
                and not isinstance(child, bool)
            ):
                findings.append(child_path)
            findings.extend(_find_literal_secret_fields(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_find_literal_secret_fields(child, f"{path}[{index}]"))

    return findings


def test_example_config_contains_only_secret_references() -> None:
    """The example uses an env-var name and contains no literal secret fields."""
    raw_text = _EXAMPLE_CONFIG_PATH.read_text(encoding="utf-8")
    config = yaml.safe_load(raw_text)

    assert isinstance(config, dict), "root must be a YAML mapping"

    secret_field_paths = _find_literal_secret_fields(config)
    assert not secret_field_paths, (
        "literal secret field is forbidden at " + ", ".join(secret_field_paths)
    )

    access_channels = config.get("access_channels")
    assert isinstance(access_channels, dict), "root.access_channels must be a mapping"

    api = access_channels.get("api")
    assert isinstance(api, dict), "root.access_channels.api must be a mapping"

    token_env_var_path = "root.access_channels.api.token_env_var"
    assert "token_env_var" in api, f"{token_env_var_path} must exist"

    token_env_var = api["token_env_var"]
    assert isinstance(token_env_var, str) and token_env_var, (
        f"{token_env_var_path} must be a non-empty string"
    )
    assert _ENV_VAR_NAME_PATTERN.fullmatch(token_env_var), (
        f"{token_env_var_path} must be an environment variable name"
    )

    api_field_names = {str(key).casefold() for key in api}
    for forbidden_name in ("token", "api_token"):
        forbidden_path = f"root.access_channels.api.{forbidden_name}"
        assert forbidden_name not in api_field_names, f"{forbidden_path} must be absent"
