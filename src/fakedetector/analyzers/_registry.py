"""Deterministic analyzer registration and configuration validation."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError
from pydantic_core import PydanticSerializationError

from fakedetector.analyzers._catalog import _resolve_worker_definition, _WorkerDefinitionResolver
from fakedetector.analyzers._errors import AnalyzerConfigurationError
from fakedetector.analyzers._models import AnalyzerRegistration
from fakedetector.analyzers._transport import _MAX_SETTINGS_BYTES
from fakedetector.config._snapshot import _ConfigSnapshot
from fakedetector.config.models import AppConfig
from fakedetector.domain import MediaType
from fakedetector.preprocessing._requirements import PreprocessingRequirements

_SAFE_ANALYZER_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SAFE_CANDIDATE_TYPE = re.compile(r"^[a-z][a-z0-9_]{0,127}$")
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
        *,
        _definition_resolver: _WorkerDefinitionResolver | None = None,
    ) -> None:
        self._config_snapshot = _ConfigSnapshot.capture(config)
        captured_config = self._config_snapshot.materialize()
        if (
            captured_config.analyzers.defaults.continue_on_error
            is not captured_config.error_handling.continue_if_analyzer_fails
        ):
            raise AnalyzerConfigurationError("continue_policy")

        registered = tuple(registrations)
        by_id: dict[str, AnalyzerRegistration] = {}
        for registration in registered:
            self._validate_registration(registration, _definition_resolver)
            if registration.analyzer_id in by_id:
                raise AnalyzerConfigurationError("duplicate_registration")
            by_id[registration.analyzer_id] = registration

        unknown_settings = set(captured_config.analyzers.settings) - set(by_id)
        if unknown_settings:
            raise AnalyzerConfigurationError("unknown_settings")
        settings_by_id = {
            analyzer_id: self._validated_settings_json(
                registration,
                captured_config.analyzers.settings.get(analyzer_id, {}),
            )
            for analyzer_id, registration in by_id.items()
        }

        plans: dict[MediaType, tuple[_ActiveAnalyzer, ...]] = {}
        for media_type, enabled in (
            (MediaType.IMAGE, captured_config.analyzers.image.enabled),
            (MediaType.AUDIO, captured_config.analyzers.audio.enabled),
            (MediaType.VIDEO, captured_config.analyzers.video.enabled),
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
        self._timeout_seconds = float(captured_config.analyzers.defaults.timeout_seconds)
        self._continue_on_failure = captured_config.error_handling.continue_if_analyzer_fails

    def _uses_config_snapshot(self, snapshot: _ConfigSnapshot) -> bool:
        return self._config_snapshot == snapshot

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

    def active_analyzer_ids(self, media_type: MediaType) -> tuple[str, ...]:
        """Return the validated completeness plan in deterministic config order."""
        return tuple(active.registration.analyzer_id for active in self.active_plan(media_type))

    def preprocessing_requirements(
        self,
        media_type: MediaType,
    ) -> PreprocessingRequirements:
        """Aggregate only declarations from analyzers active for one media route."""
        plan = self.active_plan(media_type)
        requirements = PreprocessingRequirements.aggregate(
            active.registration.preprocessing_requirements for active in plan
        )
        requirements.validate_media(media_type)
        return requirements

    @staticmethod
    def _validate_registration(
        registration: AnalyzerRegistration,
        definition_resolver: _WorkerDefinitionResolver | None = None,
    ) -> None:
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
        try:
            for media_type in registration.supported_media_types:
                requirements.validate_media(media_type)
        except ValueError:
            raise AnalyzerConfigurationError("preprocessing_requirements") from None
        candidate_types = registration.candidate_finding_types
        max_candidates = registration.max_candidate_findings
        if (
            not isinstance(candidate_types, frozenset)
            or any(
                not isinstance(candidate_type, str)
                or _SAFE_CANDIDATE_TYPE.fullmatch(candidate_type) is None
                for candidate_type in candidate_types
            )
            or not isinstance(max_candidates, int)
            or isinstance(max_candidates, bool)
            or max_candidates < 0
            or (bool(candidate_types) != (max_candidates > 0))
        ):
            raise AnalyzerConfigurationError("candidate_findings")

        resolver = definition_resolver or _resolve_worker_definition
        definition = resolver(registration.worker_key)
        if definition is None:
            raise AnalyzerConfigurationError("worker_key")
        implementation = definition.factory
        if (
            registration.analyzer_id != definition.analyzer_id
            or registration.analyzer_name != definition.analyzer_name
            or registration.analyzer_version != definition.analyzer_version
            or registration.group != definition.group
            or registration.supported_media_types != definition.supported_media_types
            or registration.settings_model is not definition.settings_model
            or registration.preprocessing_requirements != definition.preprocessing_requirements
            or registration.candidate_finding_types != definition.candidate_finding_types
            or registration.max_candidate_findings != definition.max_candidate_findings
            or implementation.analyzer_id != definition.analyzer_id
            or implementation.analyzer_name != definition.analyzer_name
            or implementation.analyzer_version != definition.analyzer_version
            or implementation.group != definition.group
            or implementation.supported_media_types != definition.supported_media_types
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
