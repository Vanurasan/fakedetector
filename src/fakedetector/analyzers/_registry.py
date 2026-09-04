"""Deterministic analyzer registration and configuration validation."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError
from pydantic_core import PydanticSerializationError

from fakedetector.analyzers._catalog import _resolve_worker_definition
from fakedetector.analyzers._errors import AnalyzerConfigurationError
from fakedetector.analyzers._models import AnalyzerRegistration
from fakedetector.analyzers._transport import _MAX_SETTINGS_BYTES
from fakedetector.config.models import AppConfig
from fakedetector.domain import MediaType
from fakedetector.preprocessing._requirements import PreprocessingRequirements

_SAFE_ANALYZER_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MAX_METADATA_TEXT_CHARS = 128


@dataclass(frozen=True, slots=True)
class _ActiveAnalyzer:
    registration: AnalyzerRegistration
    settings_json: str = field(repr=False)


class AnalyzerRegistry:
    """Immutable active plans derived from trusted registrations and AppConfig."""

    def __init__(
        self,
        config: AppConfig,
        registrations: Sequence[AnalyzerRegistration],
    ) -> None:
        if (
            config.analyzers.defaults.continue_on_error
            is not config.error_handling.continue_if_analyzer_fails
        ):
            raise AnalyzerConfigurationError("continue_policy")

        registered = tuple(registrations)
        by_id: dict[str, AnalyzerRegistration] = {}
        for registration in registered:
            self._validate_registration(registration)
            if registration.analyzer_id in by_id:
                raise AnalyzerConfigurationError("duplicate_registration")
            by_id[registration.analyzer_id] = registration

        unknown_settings = set(config.analyzers.settings) - set(by_id)
        if unknown_settings:
            raise AnalyzerConfigurationError("unknown_settings")
        settings_by_id = {
            analyzer_id: self._validated_settings_json(
                registration,
                config.analyzers.settings.get(analyzer_id, {}),
            )
            for analyzer_id, registration in by_id.items()
        }

        plans: dict[MediaType, tuple[_ActiveAnalyzer, ...]] = {}
        for media_type, enabled in (
            (MediaType.IMAGE, config.analyzers.image.enabled),
            (MediaType.AUDIO, config.analyzers.audio.enabled),
            (MediaType.VIDEO, config.analyzers.video.enabled),
        ):
            if len(enabled) != len(set(enabled)):
                raise AnalyzerConfigurationError("duplicate_enabled")
            active: list[_ActiveAnalyzer] = []
            for analyzer_id in enabled:
                enabled_registration = by_id.get(analyzer_id)
                if enabled_registration is None:
                    raise AnalyzerConfigurationError("unknown_enabled")
                if media_type not in enabled_registration.supported_media_types:
                    raise AnalyzerConfigurationError("enabled_media_mismatch")
                active.append(_ActiveAnalyzer(enabled_registration, settings_by_id[analyzer_id]))
            plans[media_type] = tuple(active)

        self._plans = plans
        self._timeout_seconds = float(config.analyzers.defaults.timeout_seconds)
        self._continue_on_failure = config.error_handling.continue_if_analyzer_fails

    @property
    def timeout_seconds(self) -> float:
        return self._timeout_seconds

    @property
    def continue_on_failure(self) -> bool:
        return self._continue_on_failure

    def active_plan(self, media_type: MediaType) -> tuple[_ActiveAnalyzer, ...]:
        """Return the exact per-media config order without sorting registrations."""
        try:
            return self._plans[media_type]
        except KeyError:
            raise AnalyzerConfigurationError("media_type") from None

    def preprocessing_requirements(
        self,
        media_type: MediaType,
    ) -> PreprocessingRequirements:
        """Aggregate only declarations from analyzers active for one media route."""
        plan = self.active_plan(media_type)
        return PreprocessingRequirements(
            audio_spectrogram=any(
                active.registration.preprocessing_requirements.audio_spectrogram for active in plan
            ),
            video_audio_track=any(
                active.registration.preprocessing_requirements.video_audio_track for active in plan
            ),
        )

    @staticmethod
    def _validate_registration(registration: AnalyzerRegistration) -> None:
        if not isinstance(registration, AnalyzerRegistration):
            raise AnalyzerConfigurationError("registration_type")
        if _SAFE_ANALYZER_ID.fullmatch(registration.analyzer_id) is None:
            raise AnalyzerConfigurationError("analyzer_id")
        if not _bounded_text(registration.analyzer_name):
            raise AnalyzerConfigurationError("analyzer_name")
        if not _bounded_text(registration.analyzer_version):
            raise AnalyzerConfigurationError("analyzer_version")
        if not _bounded_text(registration.group):
            raise AnalyzerConfigurationError("group")
        if not registration.supported_media_types or any(
            not isinstance(media_type, MediaType)
            for media_type in registration.supported_media_types
        ):
            raise AnalyzerConfigurationError("supported_media_types")
        if not isinstance(registration.settings_model, type) or not issubclass(
            registration.settings_model, BaseModel
        ):
            raise AnalyzerConfigurationError("settings_contract")
        requirements = registration.preprocessing_requirements
        if not isinstance(requirements, PreprocessingRequirements) or (
            requirements.audio_spectrogram
            and MediaType.AUDIO not in registration.supported_media_types
            or requirements.video_audio_track
            and MediaType.VIDEO not in registration.supported_media_types
        ):
            raise AnalyzerConfigurationError("preprocessing_requirements")

        definition = _resolve_worker_definition(registration.worker_key)
        if definition is None:
            raise AnalyzerConfigurationError("worker_key")
        if (
            registration.analyzer_id != definition.analyzer_id
            or registration.analyzer_name != definition.analyzer_name
            or registration.analyzer_version != definition.analyzer_version
            or registration.group != definition.group
            or registration.supported_media_types != definition.supported_media_types
            or registration.settings_model is not definition.settings_model
            or registration.preprocessing_requirements != definition.preprocessing_requirements
        ):
            raise AnalyzerConfigurationError("registration_mismatch")

    @staticmethod
    def _validated_settings_json(
        registration: AnalyzerRegistration,
        raw_settings: object,
    ) -> str:
        if not isinstance(raw_settings, Mapping):
            raise AnalyzerConfigurationError("settings_shape")
        try:
            settings = registration.settings_model.model_validate(dict(raw_settings))
            payload = json.dumps(
                settings.model_dump(mode="json"),
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except (ValidationError, PydanticSerializationError, TypeError, ValueError):
            raise AnalyzerConfigurationError("settings_validation") from None
        if len(payload.encode("utf-8")) > _MAX_SETTINGS_BYTES:
            raise AnalyzerConfigurationError("settings_size")
        return payload


def _bounded_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= _MAX_METADATA_TEXT_CHARS
