"""Tests for environment-only Stage 8 HTTP authentication adapters."""

from __future__ import annotations

from base64 import b64encode

import pytest

from fakedetector.auth import (
    AccessConfigurationError,
    APIBearerAuthenticator,
    WebUIBasicAuthenticator,
    load_api_authenticator,
    load_webui_authenticator,
)
from fakedetector.config.models import APIConfig, WebUIConfig
from fakedetector.webui import _strict_basic_credentials


@pytest.mark.parametrize("value", [None, ""])
def test_required_api_token_missing_or_empty_fails_startup(value: str | None) -> None:
    environment = {} if value is None else {"API_TOKEN": value}

    with pytest.raises(AccessConfigurationError):
        load_api_authenticator(
            APIConfig(token_env_var="API_TOKEN"),
            environ=environment,
        )


@pytest.mark.parametrize("value", [None, "", "username", ":password", "username:"])
def test_required_webui_credentials_missing_or_malformed_fail_startup(
    value: str | None,
) -> None:
    environment = {} if value is None else {"WEBUI_CREDENTIALS": value}

    with pytest.raises(AccessConfigurationError):
        load_webui_authenticator(
            WebUIConfig(credentials_env_var="WEBUI_CREDENTIALS"),
            environ=environment,
        )


def test_disabled_or_unprotected_channels_do_not_require_environment() -> None:
    assert load_api_authenticator(APIConfig(enabled=False), environ={}) is None
    assert load_api_authenticator(APIConfig(require_token=False), environ={}) is None
    assert load_webui_authenticator(WebUIConfig(enabled=False), environ={}) is None
    assert (
        load_webui_authenticator(
            WebUIConfig(require_authentication=False),
            environ={},
        )
        is None
    )


def test_authenticators_compare_exact_values() -> None:
    bearer = APIBearerAuthenticator("token")
    basic = WebUIBasicAuthenticator("analyst", "password:with-colon")

    assert bearer.verify("token")
    assert not bearer.verify("TOKEN")
    assert not bearer.verify(None)
    assert basic.verify("analyst", "password:with-colon")
    assert not basic.verify("analyst", "wrong")
    assert not basic.verify(None, None)


@pytest.mark.parametrize(
    "credentials",
    ["аналитик:password", "analyst:пароль"],
)
def test_non_ascii_webui_credentials_fail_startup(credentials: str) -> None:
    with pytest.raises(AccessConfigurationError):
        load_webui_authenticator(
            WebUIConfig(credentials_env_var="WEBUI_CREDENTIALS"),
            environ={"WEBUI_CREDENTIALS": credentials},
        )


def test_accepted_webui_credentials_round_trip_through_basic_parser() -> None:
    authenticator = load_webui_authenticator(
        WebUIConfig(credentials_env_var="WEBUI_CREDENTIALS"),
        environ={"WEBUI_CREDENTIALS": "analyst:password:with-colon"},
    )
    assert authenticator is not None
    payload = b64encode(b"analyst:password:with-colon").decode("ascii")

    username, password = _strict_basic_credentials(f"Basic {payload}")

    assert authenticator.verify(username, password)
