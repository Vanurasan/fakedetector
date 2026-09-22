"""Stage 5 Increment 4 analyzer registry and typed configuration tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from support.framework_analyzers import (
    _framework_registry,
    _framework_test_registrations,
    _resolve_framework_definition,
)

from fakedetector.analyzers._catalog import (
    _built_in_analyzer_registrations,
    _resolve_worker_definition,
)
from fakedetector.analyzers._errors import AnalyzerConfigurationError
from fakedetector.analyzers._registry import AnalyzerRegistry
from fakedetector.config.models import AppConfig
from fakedetector.domain import MediaType
from fakedetector.preprocessing._requirements import ForensicCapability, PreprocessingRequirements


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
        _framework_registry(_config(), (registration, registration))

    assert error.value.phase == "duplicate_registration"


def test_registry_rejects_unknown_enabled_analyzer() -> None:
    with pytest.raises(AnalyzerConfigurationError) as error:
        _framework_registry(
            _config(image=["not_registered"]),
            _framework_test_registrations(),
        )

    assert error.value.phase == "unknown_enabled"


def test_registry_rejects_analyzer_enabled_for_wrong_media() -> None:
    with pytest.raises(AnalyzerConfigurationError) as error:
        _framework_registry(
            _config(audio=["fake_image_analyzer"]),
            _framework_test_registrations(),
        )

    assert error.value.phase == "enabled_media_mismatch"


@pytest.mark.parametrize("analyzer_id", ["", "Bad-ID", "1_analyzer", "a" * 65])
def test_registry_rejects_invalid_analyzer_id(analyzer_id: str) -> None:
    registration = replace(_framework_test_registrations()[0], analyzer_id=analyzer_id)

    with pytest.raises(AnalyzerConfigurationError) as error:
        _framework_registry(_config(), (registration,))

    assert error.value.phase == "analyzer_id"


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "phase"),
    [
        ("analyzer_name", "", "analyzer_name"),
        ("analyzer_version", " ", "analyzer_version"),
        ("group", "x" * 129, "group"),
        ("supported_media_types", frozenset(), "supported_media_types"),
        ("settings_model", str, "settings_contract"),
        ("candidate_finding_types", frozenset({"Bad-Type"}), "candidate_findings"),
        ("max_candidate_findings", 1, "candidate_findings"),
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
        _framework_registry(_config(), (registration,))

    assert error.value.phase == phase


def test_registry_rejects_non_registration_object() -> None:
    with pytest.raises(AnalyzerConfigurationError) as error:
        _framework_registry(_config(), (object(),))

    assert error.value.phase == "registration_type"


def test_registry_rejects_registration_media_declaration_mismatch() -> None:
    registration = replace(
        _framework_test_registrations()[0],
        supported_media_types=frozenset({MediaType.AUDIO}),
    )

    with pytest.raises(AnalyzerConfigurationError) as error:
        _framework_registry(_config(), (registration,))

    assert error.value.phase == "registration_mismatch"


def test_registry_rejects_catalog_implementation_identity_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registration = _framework_test_registrations()[0]
    definition = _resolve_framework_definition(registration.worker_key)
    assert definition is not None
    monkeypatch.setattr(definition.factory, "analyzer_version", "9.9.9")

    with pytest.raises(AnalyzerConfigurationError) as error:
        _framework_registry(_config(), (registration,))

    assert error.value.phase == "registration_mismatch"


def test_registry_rejects_untrusted_worker_key() -> None:
    registration = replace(
        _framework_test_registrations()[0],
        worker_key="arbitrary.module:Analyzer",
    )

    with pytest.raises(AnalyzerConfigurationError) as error:
        _framework_registry(_config(), (registration,))

    assert error.value.phase == "worker_key"


def test_registry_preserves_exact_config_order() -> None:
    configured_order = ["fake_image_second_analyzer", "fake_image_analyzer"]
    registry = _framework_registry(
        _config(image=configured_order),
        tuple(reversed(_framework_test_registrations())),
    )

    assert [
        active.registration.analyzer_id for active in registry.active_plan(MediaType.IMAGE)
    ] == configured_order
    assert registry.active_analyzer_ids(MediaType.IMAGE) == tuple(configured_order)


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
        _framework_registry(
            _config(image=["fake_image_analyzer"], settings=settings),
            _framework_test_registrations(),
        )

    assert error.value.phase in {"settings_shape", "settings_validation"}
    assert str(error.value) == "Analyzer configuration is invalid."
    assert "not-a-bool" not in str(error.value)


def test_registry_rejects_settings_for_unknown_analyzer() -> None:
    with pytest.raises(AnalyzerConfigurationError) as error:
        _framework_registry(
            _config(settings={"unknown": {"secret": "do-not-expose"}}),
            _framework_test_registrations(),
        )

    assert error.value.phase == "unknown_settings"
    assert "do-not-expose" not in str(error.value)


def test_registry_accepts_valid_typed_settings_and_equal_continue_policy() -> None:
    registry = _framework_registry(
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
        _framework_registry(
            _config(continue_on_failure=True, legacy_continue=False),
            _framework_test_registrations(),
        )

    assert error.value.phase == "continue_policy"


def test_registry_rejects_duplicate_enabled_id() -> None:
    with pytest.raises(AnalyzerConfigurationError) as error:
        _framework_registry(
            _config(image=["fake_image_analyzer", "fake_image_analyzer"]),
            _framework_test_registrations(),
        )

    assert error.value.phase == "duplicate_enabled"


def test_registry_derives_requirements_only_from_enabled_analyzers() -> None:
    registry = _framework_registry(
        _config(
            image=["fake_image_analyzer"],
            audio=["fake_audio_analyzer"],
            video=["fake_video_analyzer"],
        ),
        _framework_test_registrations(),
    )

    image = registry.preprocessing_requirements(MediaType.IMAGE)
    audio = registry.preprocessing_requirements(MediaType.AUDIO)
    video = registry.preprocessing_requirements(MediaType.VIDEO)

    assert not image.audio_spectrogram
    assert not image.video_audio_track
    assert audio.audio_spectrogram
    assert not audio.video_audio_track
    assert not video.audio_spectrogram
    assert video.video_audio_track
    assert not image.forensic and not audio.forensic and not video.forensic


def test_forensic_demand_is_closed_deduplicated_and_current_catalog_remains_inactive():
    cap = ForensicCapability
    request = PreprocessingRequirements(forensic=frozenset({cap.JPEG_COEFFICIENTS}))
    assert request.forensic == frozenset(
        {cap.JPEG_COEFFICIENTS, cap.JPEG_STRUCTURE, cap.IMAGE_COORDINATES, cap.ORIGINAL_IMAGE}
    )
    assert PreprocessingRequirements.aggregate((request, request)) == request
    assert PreprocessingRequirements.aggregate(()) == PreprocessingRequirements()
    av = PreprocessingRequirements(forensic=frozenset({cap.AV_TIMELINE}))
    assert av.forensic == frozenset(
        {
            cap.AV_TIMELINE,
            cap.TIMING_RECORDS,
            cap.STREAM_TIMING,
        }
    )
    av.validate_media(MediaType.VIDEO)
    with pytest.raises(ValueError):
        av.validate_media(MediaType.AUDIO)
    production = _built_in_analyzer_registrations()
    assert {r.analyzer_id for r in production} == {
        "image_metadata_consistency",
        "image_copy_move_correspondence",
        "audio_pcm_quality",
        "video_sampled_frame_quality",
    }
    config = _config(
        image=[r.analyzer_id for r in production if MediaType.IMAGE in r.supported_media_types],
        audio=[r.analyzer_id for r in production if MediaType.AUDIO in r.supported_media_types],
        video=[r.analyzer_id for r in production if MediaType.VIDEO in r.supported_media_types],
    )
    registry = AnalyzerRegistry(config, production)
    for registration in production:
        assert registration.analyzer_version == "1.0.0"
        assert registration.preprocessing_requirements == PreprocessingRequirements()
    for media_type in MediaType:
        assert registry.preprocessing_requirements(media_type) == PreprocessingRequirements()


def test_registry_aggregates_future_demands_only_for_enabled_definitions():
    cap = ForensicCapability
    registrations = tuple(
        replace(
            r,
            preprocessing_requirements=PreprocessingRequirements(
                forensic=frozenset({cap.JPEG_COEFFICIENTS if index == 0 else cap.RESIDUAL_RASTER}),
            ),
        )
        for index, r in enumerate(_framework_test_registrations()[:2])
    )
    definitions = {}
    for registration in registrations:
        definitions[registration.worker_key] = replace(
            _resolve_framework_definition(registration.worker_key),
            preprocessing_requirements=registration.preprocessing_requirements,
        )
    registry = AnalyzerRegistry(
        _config(image=[registrations[0].analyzer_id]),
        registrations,
        _definition_resolver=definitions.get,
    )
    assert registry.preprocessing_requirements(MediaType.IMAGE) == (
        registrations[0].preprocessing_requirements
    )
    assert cap.RESIDUAL_RASTER not in registry.preprocessing_requirements(MediaType.IMAGE).forensic
    bad = replace(
        registrations[0],
        preprocessing_requirements=PreprocessingRequirements(
            forensic=frozenset({cap.AUDIO_SAMPLES}),
        ),
    )
    with pytest.raises(AnalyzerConfigurationError) as error:
        AnalyzerRegistry(_config(), (bad,), _definition_resolver=definitions.get)
    assert error.value.phase == "preprocessing_requirements"


@pytest.mark.parametrize(
    "invalid",
    [set(), [ForensicCapability.ORIGINAL_IMAGE], frozenset({"original_image"}), frozenset({1})],
)
def test_forensic_requirements_are_typed_and_immutable(invalid):
    with pytest.raises(TypeError):
        PreprocessingRequirements(forensic=invalid)


def test_disabled_analyzer_does_not_contribute_preprocessing_requirements() -> None:
    registry = _framework_registry(_config(), _framework_test_registrations())

    assert registry.preprocessing_requirements(MediaType.AUDIO) == PreprocessingRequirements()
    assert registry.preprocessing_requirements(MediaType.VIDEO) == PreprocessingRequirements()


def test_registry_rejects_requirement_for_unsupported_media() -> None:
    registration = replace(
        _framework_test_registrations()[0],
        preprocessing_requirements=PreprocessingRequirements(audio_spectrogram=True),
    )

    with pytest.raises(AnalyzerConfigurationError) as error:
        _framework_registry(_config(), (registration,))

    assert error.value.phase == "preprocessing_requirements"


@pytest.mark.parametrize("registration", _framework_test_registrations())
def test_production_catalog_and_registry_reject_every_framework_worker(registration) -> None:
    assert _resolve_worker_definition(registration.worker_key) is None
    with pytest.raises(AnalyzerConfigurationError) as error:
        AnalyzerRegistry(_config(), (registration,))
    assert error.value.phase == "worker_key"
