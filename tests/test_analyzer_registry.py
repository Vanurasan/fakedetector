"""Stage 5 Increment 4 analyzer registry and typed configuration tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from fakedetector.analyzers._catalog import _framework_test_registrations
from fakedetector.analyzers._errors import AnalyzerConfigurationError
from fakedetector.analyzers._registry import AnalyzerRegistry
from fakedetector.config.models import AppConfig
from fakedetector.domain import MediaType


def _config(
    *,
    image: list[str] | None = None,
    audio: list[str] | None = None,
    video: list[str] | None = None,
    settings: dict[str, object] | None = None,
    continue_on_failure: bool = True,
    legacy_continue: bool | None = None,
) -> AppConfig:
    raw = yaml.safe_load(Path("config/config.example.yaml").read_text(encoding="utf-8"))
    raw["analyzers"]["image"]["enabled"] = image or []
    raw["analyzers"]["audio"]["enabled"] = audio or []
    raw["analyzers"]["video"]["enabled"] = video or []
    raw["analyzers"]["settings"] = settings or {}
    raw["analyzers"]["defaults"]["continue_on_error"] = (
        continue_on_failure if legacy_continue is None else legacy_continue
    )
    raw["error_handling"]["continue_if_analyzer_fails"] = continue_on_failure
    return AppConfig.model_validate(raw)


def test_registry_rejects_duplicate_registration_without_overwrite() -> None:
    registration = _framework_test_registrations()[0]

    with pytest.raises(AnalyzerConfigurationError) as error:
        AnalyzerRegistry(_config(), (registration, registration))

    assert error.value.phase == "duplicate_registration"


def test_registry_rejects_unknown_enabled_analyzer() -> None:
    with pytest.raises(AnalyzerConfigurationError) as error:
        AnalyzerRegistry(
            _config(image=["not_registered"]),
            _framework_test_registrations(),
        )

    assert error.value.phase == "unknown_enabled"


def test_registry_rejects_analyzer_enabled_for_wrong_media() -> None:
    with pytest.raises(AnalyzerConfigurationError) as error:
        AnalyzerRegistry(
            _config(audio=["fake_image_analyzer"]),
            _framework_test_registrations(),
        )

    assert error.value.phase == "enabled_media_mismatch"


@pytest.mark.parametrize("analyzer_id", ["", "Bad-ID", "1_analyzer", "a" * 65])
def test_registry_rejects_invalid_analyzer_id(analyzer_id: str) -> None:
    registration = replace(_framework_test_registrations()[0], analyzer_id=analyzer_id)

    with pytest.raises(AnalyzerConfigurationError) as error:
        AnalyzerRegistry(_config(), (registration,))

    assert error.value.phase == "analyzer_id"


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "phase"),
    [
        ("analyzer_name", "", "analyzer_name"),
        ("analyzer_version", " ", "analyzer_version"),
        ("group", "x" * 129, "group"),
        ("supported_media_types", frozenset(), "supported_media_types"),
        ("settings_model", str, "settings_contract"),
    ],
)
def test_registry_rejects_invalid_registration_contract(
    field_name: str,
    invalid_value: object,
    phase: str,
) -> None:
    registration = replace(
        _framework_test_registrations()[0],
        **{field_name: invalid_value},
    )

    with pytest.raises(AnalyzerConfigurationError) as error:
        AnalyzerRegistry(_config(), (registration,))

    assert error.value.phase == phase


def test_registry_rejects_non_registration_object() -> None:
    with pytest.raises(AnalyzerConfigurationError) as error:
        AnalyzerRegistry(_config(), (object(),))

    assert error.value.phase == "registration_type"


def test_registry_rejects_registration_media_declaration_mismatch() -> None:
    registration = replace(
        _framework_test_registrations()[0],
        supported_media_types=frozenset({MediaType.AUDIO}),
    )

    with pytest.raises(AnalyzerConfigurationError) as error:
        AnalyzerRegistry(_config(), (registration,))

    assert error.value.phase == "registration_mismatch"


def test_registry_rejects_untrusted_worker_key() -> None:
    registration = replace(
        _framework_test_registrations()[0],
        worker_key="arbitrary.module:Analyzer",
    )

    with pytest.raises(AnalyzerConfigurationError) as error:
        AnalyzerRegistry(_config(), (registration,))

    assert error.value.phase == "worker_key"


def test_registry_preserves_exact_config_order() -> None:
    configured_order = ["fake_image_second_analyzer", "fake_image_analyzer"]
    registry = AnalyzerRegistry(
        _config(image=configured_order),
        tuple(reversed(_framework_test_registrations())),
    )

    assert [
        active.registration.analyzer_id for active in registry.active_plan(MediaType.IMAGE)
    ] == configured_order


@pytest.mark.parametrize(
    "settings",
    [
        {"fake_image_analyzer": "not-an-object"},
        {"fake_image_analyzer": {"applicable": "not-a-bool"}},
        {"fake_image_analyzer": {"applicable": "false"}},
        {"fake_image_analyzer": {"unknown": True}},
    ],
)
def test_registry_rejects_invalid_typed_settings_without_raw_value(
    settings: dict[str, object],
) -> None:
    with pytest.raises(AnalyzerConfigurationError) as error:
        AnalyzerRegistry(
            _config(image=["fake_image_analyzer"], settings=settings),
            _framework_test_registrations(),
        )

    assert error.value.phase in {"settings_shape", "settings_validation"}
    assert str(error.value) == "Analyzer configuration is invalid."
    assert "not-a-bool" not in str(error.value)


def test_registry_rejects_settings_for_unknown_analyzer() -> None:
    with pytest.raises(AnalyzerConfigurationError) as error:
        AnalyzerRegistry(
            _config(settings={"unknown": {"secret": "do-not-expose"}}),
            _framework_test_registrations(),
        )

    assert error.value.phase == "unknown_settings"
    assert "do-not-expose" not in str(error.value)


def test_registry_accepts_valid_typed_settings_and_equal_continue_policy() -> None:
    registry = AnalyzerRegistry(
        _config(
            image=["fake_image_analyzer"],
            settings={"fake_image_analyzer": {"applicable": False}},
            continue_on_failure=False,
        ),
        _framework_test_registrations(),
    )

    active = registry.active_plan(MediaType.IMAGE)
    assert len(active) == 1
    assert active[0].settings_json == '{"applicable":false}'
    assert registry.continue_on_failure is False


def test_registry_rejects_mismatched_duplicate_continue_policy() -> None:
    with pytest.raises(AnalyzerConfigurationError) as error:
        AnalyzerRegistry(
            _config(continue_on_failure=True, legacy_continue=False),
            _framework_test_registrations(),
        )

    assert error.value.phase == "continue_policy"


def test_registry_rejects_duplicate_enabled_id() -> None:
    with pytest.raises(AnalyzerConfigurationError) as error:
        AnalyzerRegistry(
            _config(image=["fake_image_analyzer", "fake_image_analyzer"]),
            _framework_test_registrations(),
        )

    assert error.value.phase == "duplicate_enabled"
