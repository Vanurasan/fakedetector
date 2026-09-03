"""Stage 5 Increment 4 orchestration and capability-isolation tests."""

from __future__ import annotations

import json
import pickle
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, fields, is_dataclass, replace
from io import BytesIO, UnsupportedOperation
from pathlib import Path

import pytest
import yaml

import fakedetector
import fakedetector.analyzers as analyzers_package
import fakedetector.domain as domain
from fakedetector.analyzers._catalog import (
    _framework_test_registrations,
    _resolve_worker_definition,
)
from fakedetector.analyzers._errors import AnalyzerInfrastructureError
from fakedetector.analyzers._models import (
    AnalyzerArtifactInput,
    AnalyzerRequest,
    _ReadOnlyAnalyzerInput,
)
from fakedetector.analyzers._orchestrator import AnalyzerOrchestrator, _WorkerRunner
from fakedetector.analyzers._registry import AnalyzerRegistry
from fakedetector.analyzers._transport import (
    _MAX_ARTIFACTS,
    _WorkerRequest,
    _WorkerResponseKind,
)
from fakedetector.analyzers._worker import (
    _encode_response,
    _execute_worker,
    _WorkerRun,
    _WorkerRunKind,
)
from fakedetector.config.models import AppConfig
from fakedetector.domain import (
    AnalyzerResult,
    AnalyzerStatus,
    AudioTechnicalParameters,
    ImageTechnicalParameters,
    MediaType,
    ValidatedFileDescriptor,
    VideoTechnicalParameters,
)
from fakedetector.intake.temporary_input import (
    AcceptedSource,
    LocalTemporaryInputOwner,
    PreparedSourceRef,
)
from fakedetector.lifecycle.artifacts import (
    WorkspaceArtifactRef,
    WorkspaceArtifactRegistry,
)
from fakedetector.lifecycle.models import AnalysisTask
from fakedetector.preprocessing._models import PreparedArtifact, PreparedMedia


@dataclass(slots=True)
class _PreparedCase:
    prepared: PreparedMedia
    descriptor: ValidatedFileDescriptor
    accepted_source: AcceptedSource
    registry: WorkspaceArtifactRegistry


@contextmanager
def _prepared_case(
    tmp_path: Path,
    media_type: MediaType = MediaType.IMAGE,
) -> Iterator[_PreparedCase]:
    analysis_id = f"{media_type.value[0]}" * 32
    root = tmp_path / media_type.value
    owner = LocalTemporaryInputOwner(root)
    owned = owner.create(analysis_id)
    owner.ingest(owned, BytesIO(b"controlled-source"), 100)
    accepted = owner.transfer(owned)
    registry = WorkspaceArtifactRegistry(root / analysis_id)
    artifact_ref = registry.register("prepared_input", "preprocessing/prepared.bin")

    def write_artifact(path: Path) -> None:
        path.parent.mkdir(parents=True)
        path.write_bytes(b"prepared-artifact")

    registry.with_local_artifact_path(artifact_ref, write_artifact)
    artifact = PreparedArtifact(
        artifact_id="prepared_input",
        artifact_type="normalized_input",
        artifact_ref=artifact_ref,
        format="bin",
    )
    prepared = PreparedMedia(
        analysis_id=analysis_id,
        media_type=media_type,
        source_file_ref=PreparedSourceRef(accepted),
        artifacts=(artifact,),
        metadata={"quality": {"usable": True}},
        warnings=("bounded test warning",),
    )
    case = _PreparedCase(prepared, _descriptor(media_type), accepted, registry)
    try:
        yield case
    finally:
        assert registry.cleanup_once().completed
        accepted.cleanup()


def _descriptor(media_type: MediaType) -> ValidatedFileDescriptor:
    if media_type is MediaType.IMAGE:
        parameters = ImageTechnicalParameters(
            width=1,
            height=1,
            format="PNG",
            color_mode="RGB",
            has_metadata=False,
        )
        extension = "png"
        detected_mime_type = "image/png"
    elif media_type is MediaType.AUDIO:
        parameters = AudioTechnicalParameters(
            duration_seconds=1.0,
            sample_rate_hz=8_000,
            channels=1,
            codec="pcm_s16le",
        )
        extension = "wav"
        detected_mime_type = "audio/wav"
    else:
        parameters = VideoTechnicalParameters(
            duration_seconds=1.0,
            container="mp4",
            video_codec="mpeg4",
            width=16,
            height=16,
            fps=10.0,
            has_audio=False,
        )
        extension = "mp4"
        detected_mime_type = "video/mp4"
    return ValidatedFileDescriptor(
        original_name=f"source.{extension}",
        extension=extension,
        declared_mime_type=None,
        detected_mime_type=detected_mime_type,
        media_type=media_type,
        size_bytes=17,
        sha256="0" * 64,
        signature_match=True,
        safe_read=True,
        technical_parameters=parameters,
    )


def _config(
    media_type: MediaType,
    enabled: list[str],
    *,
    settings: dict[str, object] | None = None,
    continue_on_failure: bool = True,
) -> AppConfig:
    raw = yaml.safe_load(Path("config/config.example.yaml").read_text(encoding="utf-8"))
    raw["analyzers"][media_type.value]["enabled"] = enabled
    raw["analyzers"]["settings"] = settings or {}
    raw["analyzers"]["defaults"]["timeout_seconds"] = 1
    raw["analyzers"]["defaults"]["continue_on_error"] = continue_on_failure
    raw["error_handling"]["continue_if_analyzer_fails"] = continue_on_failure
    return AppConfig.model_validate(raw)


def _orchestrator(
    config: AppConfig,
    *,
    runner: _WorkerRunner | None = None,
) -> AnalyzerOrchestrator:
    registry = AnalyzerRegistry(config, _framework_test_registrations())
    if runner is None:
        return AnalyzerOrchestrator(registry)
    return AnalyzerOrchestrator(registry, runner=runner)


@pytest.mark.parametrize(
    ("media_type", "analyzer_id"),
    [
        (MediaType.IMAGE, "fake_image_analyzer"),
        (MediaType.AUDIO, "fake_audio_analyzer"),
        (MediaType.VIDEO, "fake_video_analyzer"),
    ],
)
def test_applicable_fake_analyzer_completes_for_each_media_route(
    tmp_path: Path,
    media_type: MediaType,
    analyzer_id: str,
) -> None:
    with _prepared_case(tmp_path, media_type) as case:
        obligations_before = case.registry.cleanup_obligations()
        results = _orchestrator(_config(media_type, [analyzer_id])).execute(
            case.prepared,
            case.descriptor,
            case.registry,
        )
        assert case.registry.cleanup_obligations() == obligations_before

    assert isinstance(results, tuple)
    assert isinstance(results[0], AnalyzerResult)
    assert [result.analyzer_id for result in results] == [analyzer_id]
    assert results[0].status is AnalyzerStatus.COMPLETED
    assert results[0].score is None
    assert results[0].score_name is None
    assert results[0].candidate_findings == []


def test_several_analyzers_execute_sequentially_in_config_order(tmp_path: Path) -> None:
    enabled = ["fake_image_second_analyzer", "fake_image_analyzer"]
    with _prepared_case(tmp_path) as case:
        results = _orchestrator(_config(MediaType.IMAGE, enabled)).execute(
            case.prepared,
            case.descriptor,
            case.registry,
        )

    assert [result.analyzer_id for result in results] == enabled
    assert all(result.status is AnalyzerStatus.COMPLETED for result in results)


def test_enabled_non_applicable_analyzer_returns_canonical_result(tmp_path: Path) -> None:
    settings = {"fake_image_analyzer": {"applicable": False}}
    with _prepared_case(tmp_path) as case:
        results = _orchestrator(
            _config(MediaType.IMAGE, ["fake_image_analyzer"], settings=settings)
        ).execute(case.prepared, case.descriptor, case.registry)

    assert len(results) == 1
    assert results[0].status is AnalyzerStatus.NOT_APPLICABLE
    assert results[0].applicable is False
    assert results[0].errors == []


class _ForbiddenRunner:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, request: _WorkerRequest, timeout_seconds: float) -> _WorkerRun:
        del request, timeout_seconds
        self.calls += 1
        raise AssertionError("disabled analyzer created a worker")


def test_disabled_analyzer_creates_no_result_and_no_worker(tmp_path: Path) -> None:
    runner = _ForbiddenRunner()
    with _prepared_case(tmp_path) as case:
        results = _orchestrator(
            _config(MediaType.IMAGE, []),
            runner=runner,
        ).execute(case.prepared, case.descriptor, case.registry)

    assert results == ()
    assert runner.calls == 0


class _ContractResultRunner:
    def run(self, request: _WorkerRequest, timeout_seconds: float) -> _WorkerRun:
        assert timeout_seconds == request.timeout_seconds
        definition = _resolve_worker_definition(request.worker_key)
        assert definition is not None
        result = AnalyzerResult(
            analyzer_id=definition.analyzer_id,
            analyzer_version=definition.analyzer_version,
            media_type=MediaType(request.media_type),
            group=definition.group,
            status=AnalyzerStatus.COMPLETED,
            applicable=True,
            started_at=None,
            finished_at=None,
            duration_ms=0,
            score=0.42,
            score_name="contract_signal",
            summary="Contract probe completed.",
            raw_metrics={},
            candidate_findings=[{"type": "contract_probe", "confidence": 0.42}],
            warnings=[],
            errors=[],
        )
        return _WorkerRun(
            _WorkerRunKind.RESPONSE,
            duration_ms=3,
            response=_encode_response(
                _WorkerResponseKind.RESULT,
                result=json.loads(result.model_dump_json()),
            ),
        )


def test_orchestrator_accepts_contractual_score_and_findings(tmp_path: Path) -> None:
    with _prepared_case(tmp_path) as case:
        results = _orchestrator(
            _config(MediaType.IMAGE, ["fake_image_analyzer"]),
            runner=_ContractResultRunner(),
        ).execute(case.prepared, case.descriptor, case.registry)

    assert results[0].score == 0.42
    assert results[0].score_name == "contract_signal"
    assert results[0].candidate_findings == [{"type": "contract_probe", "confidence": 0.42}]


@pytest.mark.parametrize("continue_on_failure", [True, False])
def test_analyzer_error_obeys_continue_policy(
    tmp_path: Path,
    continue_on_failure: bool,
) -> None:
    enabled = ["fake_error_analyzer", "fake_image_analyzer"]
    with _prepared_case(tmp_path) as case:
        results = _orchestrator(
            _config(
                MediaType.IMAGE,
                enabled,
                continue_on_failure=continue_on_failure,
            )
        ).execute(case.prepared, case.descriptor, case.registry)

    assert results[0].status is AnalyzerStatus.ERROR
    assert results[0].errors[0].code == "analyzer_error"
    assert [result.analyzer_id for result in results] == (
        enabled if continue_on_failure else enabled[:1]
    )


@pytest.mark.parametrize("continue_on_failure", [True, False])
def test_analyzer_timeout_obeys_continue_policy(
    tmp_path: Path,
    continue_on_failure: bool,
) -> None:
    enabled = ["fake_hang_analyzer", "fake_image_analyzer"]
    with _prepared_case(tmp_path) as case:
        results = _orchestrator(
            _config(
                MediaType.IMAGE,
                enabled,
                continue_on_failure=continue_on_failure,
            )
        ).execute(case.prepared, case.descriptor, case.registry)

    assert results[0].status is AnalyzerStatus.TIMEOUT
    assert results[0].errors[0].code == "analyzer_timeout"
    assert [result.analyzer_id for result in results] == (
        enabled if continue_on_failure else enabled[:1]
    )


def test_worker_exception_is_safe_and_does_not_disclose_internal_data(
    tmp_path: Path,
) -> None:
    with _prepared_case(tmp_path) as case:
        results = _orchestrator(_config(MediaType.IMAGE, ["fake_error_analyzer"])).execute(
            case.prepared, case.descriptor, case.registry
        )

    serialized = results[0].model_dump_json()
    assert results[0].status is AnalyzerStatus.ERROR
    assert "RuntimeError" not in serialized
    assert "worker-only" not in serialized
    assert str(tmp_path) not in serialized
    assert "Traceback" not in serialized


def test_worker_result_serialization_failure_becomes_safe_analyzer_error(
    tmp_path: Path,
) -> None:
    with _prepared_case(tmp_path) as case:
        results = _orchestrator(_config(MediaType.IMAGE, ["fake_serialization_analyzer"])).execute(
            case.prepared, case.descriptor, case.registry
        )

    assert results[0].status is AnalyzerStatus.ERROR
    assert results[0].errors[0].code == "analyzer_error"


def test_worker_crash_without_response_is_fatal_infrastructure_failure(
    tmp_path: Path,
) -> None:
    with _prepared_case(tmp_path) as case, pytest.raises(AnalyzerInfrastructureError) as error:
        _orchestrator(_config(MediaType.IMAGE, ["fake_crash_analyzer"])).execute(
            case.prepared,
            case.descriptor,
            case.registry,
        )

    assert error.value.phase in {"worker_response", "worker_exit", "worker_no_response"}


class _MalformedResponseRunner:
    def run(self, request: _WorkerRequest, timeout_seconds: float) -> _WorkerRun:
        del request, timeout_seconds
        return _WorkerRun(_WorkerRunKind.RESPONSE, duration_ms=1, response=b"not-json")


class _WorkerErrorResponseRunner:
    def run(self, request: _WorkerRequest, timeout_seconds: float) -> _WorkerRun:
        del request, timeout_seconds
        return _WorkerRun(
            _WorkerRunKind.RESPONSE,
            duration_ms=1,
            response=b'{"kind":"worker_error"}',
        )


def test_malformed_worker_response_is_fatal_infrastructure_failure(
    tmp_path: Path,
) -> None:
    with _prepared_case(tmp_path) as case, pytest.raises(AnalyzerInfrastructureError) as error:
        _orchestrator(
            _config(MediaType.IMAGE, ["fake_image_analyzer"]),
            runner=_MalformedResponseRunner(),
        ).execute(case.prepared, case.descriptor, case.registry)

    assert error.value.phase == "malformed_response"


def test_worker_internal_response_is_fatal_not_analyzer_error(tmp_path: Path) -> None:
    with _prepared_case(tmp_path) as case, pytest.raises(AnalyzerInfrastructureError) as error:
        _orchestrator(
            _config(MediaType.IMAGE, ["fake_image_analyzer"]),
            runner=_WorkerErrorResponseRunner(),
        ).execute(case.prepared, case.descriptor, case.registry)

    assert error.value.phase == "worker_internal"


class _ExecutingRunner:
    def __init__(self) -> None:
        self.requests: list[_WorkerRequest] = []

    def run(self, request: _WorkerRequest, timeout_seconds: float) -> _WorkerRun:
        assert timeout_seconds == request.timeout_seconds
        self.requests.append(request)
        return _WorkerRun(
            _WorkerRunKind.RESPONSE,
            duration_ms=1,
            response=_execute_worker(request),
        )


def test_controlled_source_read_failure_is_fatal_and_stops_orchestration(
    tmp_path: Path,
) -> None:
    runner = _ExecutingRunner()
    enabled = ["fake_image_analyzer", "fake_image_second_analyzer"]
    with _prepared_case(tmp_path) as case:
        case.accepted_source.with_local_source_path(lambda path: path.unlink())
        with pytest.raises(AnalyzerInfrastructureError) as error:
            _orchestrator(
                _config(MediaType.IMAGE, enabled, continue_on_failure=True),
                runner=runner,
            ).execute(case.prepared, case.descriptor, case.registry)

    assert error.value.phase == "worker_internal"
    assert len(runner.requests) == 1
    assert str(tmp_path) not in str(error.value)
    assert "OSError" not in str(error.value)


def test_artifact_transport_limit_precedes_path_callbacks_and_worker_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _ForbiddenRunner()
    with _prepared_case(tmp_path) as case:
        artifacts = list(case.prepared.artifacts)
        for index in range(_MAX_ARTIFACTS):
            artifact_id = f"overflow_{index}"
            artifacts.append(
                PreparedArtifact(
                    artifact_id=artifact_id,
                    artifact_type="normalized_input",
                    artifact_ref=case.registry.register(
                        artifact_id,
                        f"preprocessing/{artifact_id}.bin",
                    ),
                    format="bin",
                )
            )
        oversized = replace(case.prepared, artifacts=tuple(artifacts))

        def fail_if_called(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("artifact path callback started before transport bound")

        monkeypatch.setattr(
            WorkspaceArtifactRegistry,
            "with_local_artifact_path",
            fail_if_called,
        )
        with pytest.raises(AnalyzerInfrastructureError) as error:
            _orchestrator(
                _config(MediaType.IMAGE, ["fake_image_analyzer"]),
                runner=runner,
            ).execute(oversized, case.descriptor, case.registry)

    assert error.value.phase == "worker_request"
    assert runner.calls == 0


class _CapturingRunner:
    def __init__(self) -> None:
        self.requests: list[_WorkerRequest] = []

    def run(self, request: _WorkerRequest, timeout_seconds: float) -> _WorkerRun:
        assert timeout_seconds == request.timeout_seconds
        assert Path(request.source_path).is_file()
        assert all(Path(artifact.local_path).is_file() for artifact in request.artifacts)
        self.requests.append(request)
        return _WorkerRun(
            _WorkerRunKind.RESPONSE,
            duration_ms=3,
            response=_execute_worker(request),
        )


def test_worker_request_is_picklable_capability_free_and_built_inside_callbacks(
    tmp_path: Path,
) -> None:
    runner = _CapturingRunner()
    with _prepared_case(tmp_path) as case:
        results = _orchestrator(
            _config(MediaType.IMAGE, ["fake_image_analyzer"]),
            runner=runner,
        ).execute(case.prepared, case.descriptor, case.registry)

        request = runner.requests[0]
        restored = pickle.loads(pickle.dumps(request))
        graph = tuple(_walk_graph(request))
        assert restored == request
        assert not any(
            isinstance(
                value,
                (
                    PreparedSourceRef,
                    WorkspaceArtifactRef,
                    WorkspaceArtifactRegistry,
                    AnalysisTask,
                ),
            )
            for value in graph
        )
        assert not any(isinstance(value, Path) for value in graph)
        assert not any(callable(value) for value in graph)
        assert str(tmp_path) not in repr(request)

    assert results[0].status is AnalyzerStatus.COMPLETED


def test_one_runner_invocation_is_used_per_executed_analyzer_in_config_order(
    tmp_path: Path,
) -> None:
    runner = _CapturingRunner()
    enabled = ["fake_image_second_analyzer", "fake_image_analyzer"]
    with _prepared_case(tmp_path) as case:
        results = _orchestrator(
            _config(MediaType.IMAGE, enabled),
            runner=runner,
        ).execute(case.prepared, case.descriptor, case.registry)

    assert [request.worker_key for request in runner.requests] == [
        "framework_test.image_second",
        "framework_test.image",
    ]
    assert [result.analyzer_id for result in results] == enabled


def test_worker_local_analyzer_request_has_only_read_capabilities(tmp_path: Path) -> None:
    source_path = tmp_path / "source.bin"
    artifact_path = tmp_path / "artifact.bin"
    source_path.write_bytes(b"source")
    artifact_path.write_bytes(b"artifact")
    definition = _resolve_worker_definition("framework_test.image")
    assert definition is not None
    settings = definition.settings_model.model_validate({})
    source = _ReadOnlyAnalyzerInput(source_path)
    artifact_input = AnalyzerArtifactInput(
        artifact_id="prepared_input",
        artifact_type="normalized_input",
        content=_ReadOnlyAnalyzerInput(artifact_path),
        format="bin",
    )
    request = AnalyzerRequest(
        analysis_id="a" * 32,
        media_type=MediaType.IMAGE,
        validated_file=_descriptor(MediaType.IMAGE),
        source=source,
        settings=settings,
        timeout_seconds=1.0,
        artifacts=(artifact_input,),
    )

    for value in (request, request.source, request.artifacts[0].content):
        assert not any(
            hasattr(value, attribute)
            for attribute in (
                "cleanup",
                "transfer",
                "register",
                "with_local_source_path",
                "with_local_artifact_path",
                "path",
                "workspace_path",
            )
        )
    with request.source.open_for_read() as stream:
        assert stream.read() == b"source"
        with pytest.raises(UnsupportedOperation):
            stream.write(b"mutation")


def _walk_graph(value: object, seen: set[int] | None = None) -> Iterator[object]:
    active_seen = seen if seen is not None else set()
    if id(value) in active_seen:
        return
    active_seen.add(id(value))
    yield value
    if is_dataclass(value) and not isinstance(value, type):
        for model_field in fields(value):
            yield from _walk_graph(getattr(value, model_field.name), active_seen)
    elif isinstance(value, tuple):
        for item in value:
            yield from _walk_graph(item, active_seen)


def test_analyzer_framework_does_not_expand_public_facades() -> None:
    internal_names = (
        "Analyzer",
        "AnalyzerRequest",
        "AnalyzerRegistry",
        "AnalyzerOrchestrator",
        "WorkerRequest",
    )

    assert not any(hasattr(fakedetector, name) for name in internal_names)
    assert not any(hasattr(analyzers_package, name) for name in internal_names)
    assert not any(hasattr(domain, name) for name in internal_names)
    assert domain.AnalyzerResult is AnalyzerResult
    assert domain.AnalyzerStatus is AnalyzerStatus
