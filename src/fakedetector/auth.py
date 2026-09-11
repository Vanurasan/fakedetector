"""Environment-backed HTTP authentication adapters."""

from __future__ import annotations

import os
import secrets
from collections.abc import Mapping

from fakedetector.config.models import APIConfig, WebUIConfig


class AccessConfigurationError(Exception):
    """Safe startup failure for missing or malformed access credentials."""

    def __init__(self) -> None:
        super().__init__("Access channel credentials are not configured.")


class APIBearerAuthenticator:
    """Compare a supplied Bearer token with an environment-sourced secret."""

    __slots__ = ("_expected_token",)

    def __init__(self, expected_token: str) -> None:
        self._expected_token = expected_token.encode("utf-8")

    def verify(self, supplied_token: str | None) -> bool:
        candidate = b"" if supplied_token is None else supplied_token.encode("utf-8")
        return secrets.compare_digest(candidate, self._expected_token)


class WebUIBasicAuthenticator:
    """Compare supplied HTTP Basic credentials in constant time."""

    __slots__ = ("_expected_password", "_expected_username")

    def __init__(self, username: str, password: str) -> None:
        self._expected_username = username.encode("utf-8")
        self._expected_password = password.encode("utf-8")

    def verify(self, username: str | None, password: str | None) -> bool:
        supplied_username = b"" if username is None else username.encode("utf-8")
        supplied_password = b"" if password is None else password.encode("utf-8")
        username_matches = secrets.compare_digest(
            supplied_username,
            self._expected_username,
        )
        password_matches = secrets.compare_digest(
            supplied_password,
            self._expected_password,
        )
        return username_matches and password_matches


def load_api_authenticator(
    config: APIConfig,
    *,
    environ: Mapping[str, str] | None = None,
) -> APIBearerAuthenticator | None:
    """Resolve API authentication without retaining a token in configuration."""
    if not config.enabled or not config.require_token:
        return None
    values = os.environ if environ is None else environ
    token = values.get(config.token_env_var)
    if token is None or not token:
        raise AccessConfigurationError() from None
    return APIBearerAuthenticator(token)


def load_webui_authenticator(
    config: WebUIConfig,
    *,
    environ: Mapping[str, str] | None = None,
) -> WebUIBasicAuthenticator | None:
    """Resolve one ``username:password`` pair for the enabled WebUI."""
    if not config.enabled or not config.require_authentication:
        return None
    values = os.environ if environ is None else environ
    credentials = values.get(config.credentials_env_var)
    if credentials is None:
        raise AccessConfigurationError() from None
    username, separator, password = credentials.partition(":")
    if not separator or not username or not password:
        raise AccessConfigurationError() from None
    return WebUIBasicAuthenticator(username, password)
