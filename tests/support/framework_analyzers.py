"""Importable fake analyzers and explicit wiring for real spawn framework tests."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Sequence
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from fakedetector.analyzers._catalog import _definition, _WorkerAnalyzerDefinition
from fakedetector.analyzers._models import (
    AnalyzerRegistration,
    AnalyzerRequest,
    ApplicabilityResult,
)
from fakedetector.analyzers._registry import AnalyzerRegistry
from fakedetector.analyzers._transport import _WorkerRequest
from fakedetector.analyzers._worker import _execute_worker, _SpawnBackend, _SpawnedWorkerRunner
from fakedetector.config.models import AppConfig
from fakedetector.domain import AnalyzerResult, AnalyzerStatus, MediaType
from fakedetector.preprocessing._requirements import PreprocessingRequirements


class _FakeAnalyzerSettings(BaseModel):
    """Small typed settings contract used only by the framework test analyzers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    applicable: bool = Field(default=True, strict=True)


class _FakeAnalyzerBase:
    analyzer_id: ClassVar[str]
    analyzer_name: ClassVar[str]
    analyzer_version: ClassVar[str] = "1.0.0"
    group: ClassVar[str] = "framework_test"
    supported_media_types: ClassVar[frozenset[MediaType]]

    def check_applicability(self, request: AnalyzerRequest) -> ApplicabilityResult:
        settings = request.settings
        if not isinstance(settings, _FakeAnalyzerSettings):
            raise TypeError("unexpected settings contract")
        if not settings.applicable:
            return ApplicabilityResult(False, "disabled_by_test_setting")
        return ApplicabilityResult(True)

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        with request.source.open_for_read() as source:
            source.read(1)
        for artifact in request.artifacts:
            with artifact.content.open_for_read() as content:
                content.read(1)
        return _completed_result(self, request)


class _FakeImageAnalyzer(_FakeAnalyzerBase):
    analyzer_id = "fake_image_analyzer"
    analyzer_name = "Stage 5 fake image analyzer"
    supported_media_types = frozenset({MediaType.IMAGE})


class _FakeImageSecondAnalyzer(_FakeAnalyzerBase):
    analyzer_id = "fake_image_second_analyzer"
    analyzer_name = "Stage 5 second fake image analyzer"
    supported_media_types = frozenset({MediaType.IMAGE})


class _FakeAudioAnalyzer(_FakeAnalyzerBase):
    analyzer_id = "fake_audio_analyzer"
    analyzer_name = "Stage 5 fake audio analyzer"
    supported_media_types = frozenset({MediaType.AUDIO})


class _FakeVideoAnalyzer(_FakeAnalyzerBase):
    analyzer_id = "fake_video_analyzer"
    analyzer_name = "Stage 5 fake video analyzer"
    supported_media_types = frozenset({MediaType.VIDEO})


class _FakeErrorAnalyzer(_FakeAnalyzerBase):
    analyzer_id = "fake_error_analyzer"
    analyzer_name = "Stage 5 fake error analyzer"
    supported_media_types = frozenset({MediaType.IMAGE})

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        del request
        raise RuntimeError("worker-only test exception")


class _FakeHangAnalyzer(_FakeAnalyzerBase):
    analyzer_id = "fake_hang_analyzer"
    analyzer_name = "Stage 5 fake hanging analyzer"
    supported_media_types = frozenset({MediaType.IMAGE})

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        del request
        time.sleep(60.0)
        raise AssertionError("hanging analyzer unexpectedly resumed")


class _FakeCrashAnalyzer(_FakeAnalyzerBase):
    analyzer_id = "fake_crash_analyzer"
    analyzer_name = "Stage 5 fake crashing analyzer"
    supported_media_types = frozenset({MediaType.IMAGE})

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        del request
        os._exit(7)


class _FakeSerializationAnalyzer(_FakeAnalyzerBase):
    analyzer_id = "fake_serialization_analyzer"
    analyzer_name = "Stage 5 fake serialization analyzer"
    supported_media_types = frozenset({MediaType.IMAGE})

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        result = _completed_result(self, request)
        result.__dict__["raw_metrics"] = {"unsafe": object()}
        return result


_FRAMEWORK_TEST_DEFINITIONS = (
    _definition("framework_test.image", _FakeImageAnalyzer, settings_model=_FakeAnalyzerSettings),
    _definition(
        "framework_test.image_second",
        _FakeImageSecondAnalyzer,
        settings_model=_FakeAnalyzerSettings,
    ),
    _definition(
        "framework_test.audio",
        _FakeAudioAnalyzer,
        settings_model=_FakeAnalyzerSettings,
        preprocessing_requirements=PreprocessingRequirements(audio_spectrogram=True),
    ),
    _definition(
        "framework_test.video",
        _FakeVideoAnalyzer,
        settings_model=_FakeAnalyzerSettings,
        preprocessing_requirements=PreprocessingRequirements(video_audio_track=True),
    ),
    _definition("framework_test.error", _FakeErrorAnalyzer, settings_model=_FakeAnalyzerSettings),
    _definition("framework_test.hang", _FakeHangAnalyzer, settings_model=_FakeAnalyzerSettings),
    _definition("framework_test.crash", _FakeCrashAnalyzer, settings_model=_FakeAnalyzerSettings),
    _definition(
        "framework_test.serialization",
        _FakeSerializationAnalyzer,
        settings_model=_FakeAnalyzerSettings,
    ),
)


def _framework_test_registrations() -> tuple[AnalyzerRegistration, ...]:
    """Return explicit internal registrations; none are active in default config."""
    return tuple(definition.registration() for definition in _FRAMEWORK_TEST_DEFINITIONS)


def _completed_result(
    analyzer: _FakeAnalyzerBase,
    request: AnalyzerRequest,
) -> AnalyzerResult:
    return AnalyzerResult(
        analyzer_id=analyzer.analyzer_id,
        analyzer_version=analyzer.analyzer_version,
        media_type=request.media_type,
        group=analyzer.group,
        status=AnalyzerStatus.COMPLETED,
        applicable=True,
        started_at=None,
        finished_at=None,
        duration_ms=0,
        score=None,
        score_name=None,
        summary="Stage 5 framework test analyzer completed.",
        raw_metrics={},
        candidate_findings=[],
        warnings=[],
        errors=[],
    )


def _resolve_framework_definition(worker_key: str) -> _WorkerAnalyzerDefinition | None:
    return next(
        (item for item in _FRAMEWORK_TEST_DEFINITIONS if item.worker_key == worker_key), None
    )


def _framework_registry(
    config: AppConfig, registrations: Sequence[AnalyzerRegistration]
) -> AnalyzerRegistry:
    return AnalyzerRegistry(
        config, registrations, _definition_resolver=_resolve_framework_definition
    )


def _framework_runner(
    *,
    backend: _SpawnBackend | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> _SpawnedWorkerRunner:
    return _SpawnedWorkerRunner(
        backend=backend, monotonic=monotonic,
        _definition_resolver=_resolve_framework_definition,
    )


def _execute_framework_worker(request: _WorkerRequest) -> bytes:
    return _execute_worker(request, _definition_resolver=_resolve_framework_definition)
