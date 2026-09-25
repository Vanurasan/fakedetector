"""Production DQ arithmetic, frozen oracle equivalence and framework integration."""

from __future__ import annotations

import hashlib
import io
import json
import math
import tracemalloc
from contextlib import contextmanager
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from pydantic import ValidationError
from test_preprocessing import _artifact_budget, _case, _image_descriptor

from fakedetector.analyzers import _image_jpeg_dq as dq
from fakedetector.analyzers._catalog import _resolve_built_in_analyzer_definition
from fakedetector.analyzers._models import (
    AnalyzerArtifactInput,
    AnalyzerRequest,
    _AnalyzerFileFacts,
    _ReadOnlyAnalyzerInput,
)
from fakedetector.analyzers._orchestrator import _plain_json_value
from fakedetector.analyzers._transport import (
    _MAX_RESPONSE_BYTES,
    _WorkerArtifact,
    _WorkerRequest,
)
from fakedetector.analyzers._worker import _execute_worker, _SpawnedWorkerRunner
from fakedetector.config.models import ImagePreprocessingConfig, RiskAssessmentConfig
from fakedetector.domain import AnalyzerResult, AnalyzerStatus, MediaType
from fakedetector.lifecycle._assessment import CompletenessAssessmentService, RiskAssessmentService
from fakedetector.lifecycle._finding_formation import FindingFormationService
from fakedetector.preprocessing._models import (
    ForensicManifest,
    ForensicRepresentation,
    ImageCoordinates,
    JpegCoefficientsDescriptor,
    JpegComponent,
    JpegHeader,
    JpegQuantizationTable,
    NumericArtifact,
    OriginalImageFacts,
    RepresentationProvenance,
)
from fakedetector.preprocessing._service import ImagePreprocessor

with pytest.MonkeyPatch.context() as _imports:
    _imports.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    from scripts.research.jpeg_dq_rule import score as oracle_score
    from scripts.research.jpeg_measurements import histogram as oracle_histogram
    from scripts.research.jpeg_measurements import measure_dq as oracle_measure


_ANALYZER = dq.ImageJpegDoubleQuantizationAnalyzer()
_DEFINITION = _resolve_built_in_analyzer_definition(_ANALYZER.analyzer_id)
assert _DEFINITION is not None


def _synthetic(
    tmp_path,
    *,
    values=None,
    size=(256, 256),
    mode="L",
    sampling=((1, 1),),
    orientation=1,
    coding="baseline",
    valid_modes=9,
):
    header = JpegHeader(
        width=size[0],
        height=size[1],
        precision_bits=8,
        coding=coding,
        components=tuple(
            JpegComponent(
                component_id=9 - i * 3,
                horizontal_sampling=h,
                vertical_sampling=v,
                quantization_table_id=i,
            )
            for i, (h, v) in enumerate(sampling)
        ),
    )
    shapes = header.preflight(1).block_shapes
    artifacts, planes = [], []
    if values is None:
        values = np.arange(-40, 41, 5, dtype="<i4")
    for index, shape in enumerate(shapes):
        coefficients = np.zeros((*shape, 8, 8), dtype="<i4")
        for u, v in dq._MODES[:valid_modes]:
            coefficients[:, :, u, v] = np.resize(values, shape)
        path = tmp_path / f"plane_{index}"
        path.write_bytes(coefficients.tobytes())
        plane = NumericArtifact(artifact_id=f"plane_{index}", dtype="<i4", shape=coefficients.shape)
        planes.append(plane)
        artifacts.append(
            AnalyzerArtifactInput(
                artifact_id=plane.artifact_id,
                artifact_type="jpeg_coefficients",
                content=_ReadOnlyAnalyzerInput(path),
                format="forensic_raw",
            )
        )
    original = OriginalImageFacts(
        format="jpeg",
        source_mode=mode,
        coordinates=ImageCoordinates(
            native_width=size[0], native_height=size[1], orientation=orientation
        ),
        jpeg=header,
        quantization_tables=tuple(
            JpegQuantizationTable(
                table_id=i,
                precision_bits=8,
                values=tuple(range(1, 65)),
            )
            for i in range(len(sampling))
        ),
    )
    manifest = ForensicManifest(
        source_sha256="0" * 64,
        media_type=MediaType.IMAGE,
        representations=(
            ForensicRepresentation(
                provenance=RepresentationProvenance(
                    producer="fakedetector",
                    producer_version="1",
                    profile="original_image",
                    profile_version="1",
                ),
                facts=original,
            ),
            ForensicRepresentation(
                provenance=RepresentationProvenance(
                    producer="pyjpegio",
                    producer_version="0.3.0",
                    profile="jpeg_coefficients",
                    profile_version="1",
                ),
                facts=JpegCoefficientsDescriptor(header=header, planes=tuple(planes)),
            ),
        ),
    )
    descriptor = _image_descriptor(
        width=size[0], height=size[1], image_format="JPEG", color_mode=mode
    )
    return AnalyzerRequest(
        analysis_id="a" * 32,
        media_type=MediaType.IMAGE,
        file_facts=_AnalyzerFileFacts.from_validated_file(descriptor),
        source=_ReadOnlyAnalyzerInput(tmp_path / "unread_source"),
        settings=dq.ImageJpegDoubleQuantizationSettings(),
        timeout_seconds=10,
        artifacts=tuple(artifacts),
        metadata={"forensic": manifest.to_metadata()},
    )


def _worker(request):
    return _WorkerRequest(
        worker_key=_DEFINITION.worker_key,
        analysis_id=request.analysis_id,
        media_type=request.media_type.value,
        file_facts_json=request.file_facts.model_dump_json(),
        source_path=str(request.source._local_path),
        artifacts=tuple(
            _WorkerArtifact(
                artifact_id=a.artifact_id,
                artifact_type=a.artifact_type,
                local_path=str(a.content._local_path),
                format=a.format,
            )
            for a in request.artifacts
        ),
        metadata_json=json.dumps(_plain_json_value(request.metadata)),
        warnings=(),
        settings_json="{}",
        timeout_seconds=10,
    )


@pytest.mark.parametrize(
    "values",
    [
        [],
        [0],
        [-2, -2, 0, 1],
        [2, 3, 5],
        [-8, -7, -1],
        [-32768, 32767],
        [-32768, 32768],
        [-(2**31), 2**31 - 1],
    ],
)
def test_histogram_matches_frozen_oracle(values):
    array = np.asarray(values, dtype="<i4")
    assert asdict(dq._histogram(array)) == asdict(oracle_histogram(array))


def test_zero_signed_range_and_preallocation_gate(monkeypatch):
    h = dq._histogram(np.array([-2, -2, 0, 1], dtype="<i4"))
    assert (h.span, h.occupied, h.zero_fraction, h.empty_fraction) == (4, 3, 0.25, 0.25)
    original = np.bincount
    calls = []

    def count(values, *, minlength):
        calls.append(minlength)
        return original(values, minlength=minlength)

    monkeypatch.setattr(np, "bincount", count)
    assert dq._histogram(np.array([-32768, 32767], dtype="<i4")).span == 65536
    assert dq._histogram(np.array([-32768, 32768], dtype="<i4")).state == "histogram_limit"
    assert dq._histogram(np.array([-(2**31), 2**31 - 1], dtype="<i4")).span == 2**32
    assert calls == [65536]
    with pytest.raises(ValueError, match="int32"):
        dq._histogram(np.array([1.0]))


@pytest.mark.parametrize(
    "field,value,valid",
    [
        ("n", 1023, False),
        ("n", 1024, True),
        ("zero_fraction", 769 / 1024, False),
        ("zero_fraction", 768 / 1024, True),
        ("occupied", 7, False),
        ("occupied", 8, True),
        ("span", 15, False),
        ("span", 16, True),
        ("state", "constant", False),
        ("state", "no_full_blocks", False),
        ("state", "histogram_limit", False),
    ],
)
def test_support_boundaries(field, value, valid):
    h = dq._Histogram(n=1024, span=16, occupied=8, zero_fraction=0, state="measured")
    assert replace(h, **{field: value}).valid() is valid


@pytest.mark.parametrize("count", [4, 5, 6, 9])
def test_minimum_modes_and_deterministic_aggregation(tmp_path, count):
    request = _synthetic(tmp_path, valid_modes=count)
    result = _ANALYZER.analyze(request)
    oracle = oracle_measure(request)
    assert result.raw_metrics["median"] == oracle_score(oracle, "empty_fraction")
    assert result.raw_metrics["valid_mode_count"] == count
    assert result == _ANALYZER.analyze(request)
    assert result.score is result.score_name is None
    if count < 5:
        assert result.raw_metrics["median"] is None
        assert result.raw_metrics["decision"] == "insufficient_evidence"
        assert not result.candidate_findings
        assert any("insufficient_evidence" in w for w in result.warnings)
        config = RiskAssessmentConfig()
        complete = CompletenessAssessmentService(config.completeness).assess(
            [result.analyzer_id], [result]
        )
        assert complete.status.value == "complete" and complete.completed_analyzers == 1
        assert complete.missing_capabilities == []
    else:
        assert len(result.candidate_findings) == 1


@pytest.mark.parametrize(
    "measurement,positive",
    [
        (math.nextafter(0.6005747126436781, -math.inf), False),
        (0.6005747126436781, False),
        (math.nextafter(0.6005747126436781, math.inf), True),
    ],
)
def test_literal_strict_threshold(tmp_path, monkeypatch, measurement, positive):
    assert dq._THRESHOLD == 0.6005747126436781
    request = _synthetic(tmp_path)
    monkeypatch.setattr(dq, "median", lambda _: measurement)
    result = _ANALYZER.analyze(request)
    assert bool(result.candidate_findings) is positive
    assert result.raw_metrics["median"] == measurement
    if not positive:
        assert "does not confirm authenticity" in result.summary


@pytest.mark.parametrize(
    "fractions,expected",
    [
        ([0.1, 0.2, 0.4, 0.8, 0.9], 0.4),
        ([0.1, 0.2, 0.4, 0.8, 0.9, 1.0], 0.6),
    ],
)
def test_even_and_odd_median(tmp_path, monkeypatch, fractions, expected):
    request = _synthetic(tmp_path)
    measurements = iter(
        [
            dq._Histogram(
                n=1024, span=100, occupied=10, zero_fraction=0, empty_fraction=f, state="measured"
            )
            for f in fractions
        ]
        + [dq._Histogram(n=0)] * (9 - len(fractions))
    )
    monkeypatch.setattr(dq, "_histogram", lambda _: next(measurements))
    result = _ANALYZER.analyze(request)
    assert result.raw_metrics["median"] == pytest.approx(expected)


@pytest.mark.parametrize("orientation", [None, *range(1, 9)])
@pytest.mark.parametrize(
    "sampling",
    [((1, 1),), ((1, 1), (1, 1), (1, 1)), ((2, 1), (1, 1), (1, 1)), ((2, 2), (1, 1), (1, 1))],
)
def test_native_crop_sof_order_dqt_and_orientation_oracle(tmp_path, orientation, sampling):
    request = _synthetic(
        tmp_path,
        size=(263, 271),
        orientation=orientation,
        mode="L" if len(sampling) == 1 else "RGB",
        sampling=sampling,
    )
    assert _ANALYZER.check_applicability(request).applicable
    result = _ANALYZER.analyze(request)
    oracle = oracle_measure(request)
    assert result.raw_metrics["first_component"] == 9
    assert result.raw_metrics["median"] == oracle_score(oracle, "empty_fraction")
    for observed, expected in zip(result.raw_metrics["modes"], oracle, strict=True):
        assert {key: observed[key] for key in asdict(expected.histogram)} == asdict(
            expected.histogram
        )
        assert observed["q2"] == expected.q2
        assert observed["excluded_blocks"] == expected.excluded_blocks > 0
    assert len(_execute_worker(_worker(request))) < _MAX_RESPONSE_BYTES


def test_no_full_blocks_and_constant_are_insufficient(tmp_path):
    for size in ((7, 7), (256, 256)):
        request = _synthetic(tmp_path, size=size, values=np.array([0], dtype="<i4"))
        result = _ANALYZER.analyze(request)
        assert result.raw_metrics["decision"] == "insufficient_evidence"
        assert result.raw_metrics["valid_mode_count"] == 0


def test_negative_and_candidate_finding_risk_correlation(tmp_path):
    request = _synthetic(tmp_path, values=np.arange(-16, 17, dtype="<i4"))
    negative = _ANALYZER.analyze(request)
    assert negative.raw_metrics["decision"] == "no_signal"
    assert not negative.candidate_findings
    request = _synthetic(tmp_path)
    positive = _ANALYZER.analyze(request)
    findings = FindingFormationService().form_findings([positive])
    assert len(findings) == 1
    finding = findings[0]
    assert finding.type == "jpeg_recompression_pattern" and finding.severity.value == "weak"
    assert finding.localization.model_dump() == {"type": "file"}
    assert finding.correlation_group == "image_jpeg_compression_history"
    assert finding.source_score is finding.score_impact is None
    assert not finding.critical_override_eligible and finding.evidence_refs == []
    config = RiskAssessmentConfig()
    complete = CompletenessAssessmentService(config.completeness).assess(
        [positive.analyzer_id], [positive]
    )
    duplicate = finding.model_copy(update={"finding_id": "other_finding"})
    risk = RiskAssessmentService(config).assess(complete, [positive], [finding, duplicate])
    assert risk.score == 5 and risk.final_level.value == "low"
    assert risk.probability is None
    assert findings == FindingFormationService().form_findings([positive])


@pytest.mark.parametrize(
    "mode,sampling",
    [
        ("CMYK", ((1, 1),) * 4),
        ("RGB", ((1, 2), (1, 1), (1, 1))),
        (None, ((1, 1),)),
        ("RGB", ((1, 1),)),
    ],
)
def test_unsupported_source_layout(tmp_path, mode, sampling):
    request = _synthetic(tmp_path, mode=mode or "L", sampling=sampling)
    if mode is None:
        manifest = request.forensic.model_dump()
        manifest["representations"][0]["facts"]["source_mode"] = None
        request = replace(
            request, metadata={"forensic": ForensicManifest.model_validate(manifest).to_metadata()}
        )
    response = json.loads(_execute_worker(_worker(request)))
    assert response["kind"] == "result"
    result = response["result"]
    assert result["status"] == "not_applicable" and not result["applicable"]
    assert not result["candidate_findings"] and result["score"] is result["score_name"] is None


@pytest.mark.parametrize(
    "damage", ["missing", "length", "manifest", "tables", "provenance", "sha", "shape"]
)
def test_corrupt_required_inputs_never_become_findings(tmp_path, damage):
    request = _synthetic(tmp_path)
    worker = _worker(request)
    if damage == "missing":
        worker = replace(
            worker, artifacts=(replace(worker.artifacts[0], local_path=str(tmp_path / "absent")),)
        )
    elif damage == "length":
        (tmp_path / "plane_0").write_bytes(b"bad")
    elif damage == "manifest":
        worker = replace(worker, metadata_json="{}")
    else:
        manifest = request.forensic.model_dump(mode="json")
        if damage == "tables":
            manifest["representations"][0]["facts"]["quantization_tables"] = []
        elif damage == "provenance":
            manifest["representations"][1]["provenance"]["profile"] = "wrong"
        elif damage == "sha":
            manifest["source_sha256"] = "1" * 64
        elif damage == "shape":
            manifest["representations"][1]["facts"]["planes"][0]["shape"] = [1, 1, 8, 8]
        worker = replace(worker, metadata_json=json.dumps({"forensic": json.dumps(manifest)}))
    response = json.loads(_execute_worker(worker))
    assert response["kind"] in {"worker_error", "analyzer_error"}
    assert "result" not in response


def test_maximum_coefficient_plane_workspace_and_payload(tmp_path):
    request = _synthetic(tmp_path, size=(2048, 2048))
    tracemalloc.start()
    result = _ANALYZER.analyze(request)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    # Includes the 16 MiB immutable reader plus bounded numerical workspace and JSON scalars.
    assert peak < 24 * 2**20
    assert result.raw_metrics["modes"][0]["n"] == 65536
    assert len(_execute_worker(_worker(request))) < _MAX_RESPONSE_BYTES
    with pytest.raises(ValueError):
        _synthetic(tmp_path, size=(2049, 2048))


def test_settings_reject_tunable_threshold():
    with pytest.raises(ValidationError):
        dq.ImageJpegDoubleQuantizationSettings(threshold=0.5)


def test_only_first_sof_component_votes(tmp_path):
    request = _synthetic(tmp_path, mode="RGB", sampling=((1, 1),) * 3)
    plane = np.zeros((32, 32, 8, 8), dtype="<i4")
    for u, v in dq._MODES:
        plane[:, :, u, v] = np.resize(np.arange(-16, 17), (32, 32))
    (tmp_path / "plane_0").write_bytes(plane.tobytes())
    result = _ANALYZER.analyze(request)
    assert result.raw_metrics["decision"] == "no_signal"
    assert result.raw_metrics["median"] == 0
    assert all(m["empty_fraction"] > dq._THRESHOLD for m in result.raw_metrics["modes"][9:])


def test_worker_payload_exact_boundary_and_allocation_failure(tmp_path, monkeypatch):
    request = _synthetic(tmp_path, mode="RGB", sampling=((1, 1),) * 3)
    worker = _worker(request)
    result = _ANALYZER.analyze(request)
    assert len(result.raw_metrics["modes"]) == 27
    baseline = _execute_worker(worker)
    assert len(baseline) < _MAX_RESPONSE_BYTES
    padded = result.model_copy(deep=True)
    padded.summary += "x" * (_MAX_RESPONSE_BYTES - len(baseline))
    with monkeypatch.context() as patch:
        patch.setattr(dq.ImageJpegDoubleQuantizationAnalyzer, "analyze", lambda *_: padded)
        assert len(_execute_worker(worker)) == _MAX_RESPONSE_BYTES
        padded.summary += "x"
        assert json.loads(_execute_worker(worker))["kind"] == "analyzer_error"

    def exhausted(*args, **kwargs):
        raise MemoryError

    monkeypatch.setattr(np, "bincount", exhausted)
    assert json.loads(_execute_worker(worker)) == {"kind": "analyzer_error"}


@contextmanager
def _prepared(tmp_path, data, *, max_size_mb=None):
    source = tmp_path / "source_image"
    source.write_bytes(data)
    with Image.open(io.BytesIO(data)) as image:
        descriptor = _image_descriptor(
            width=image.width, height=image.height, image_format=image.format, color_mode=image.mode
        ).model_copy(update={"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)})
    case = _case(tmp_path, source, descriptor)
    if max_size_mb is not None:
        case.request = replace(
            case.request, artifact_budget=_artifact_budget(MediaType.IMAGE, max_size_mb=max_size_mb)
        )
    try:
        prepared = ImagePreprocessor(ImagePreprocessingConfig()).prepare(
            case.request, _DEFINITION.preprocessing_requirements
        )
        yield AnalyzerRequest(
            analysis_id="a" * 32,
            media_type=MediaType.IMAGE,
            file_facts=_AnalyzerFileFacts.from_validated_file(descriptor),
            source=_ReadOnlyAnalyzerInput(source),
            settings=dq.ImageJpegDoubleQuantizationSettings(),
            timeout_seconds=10,
            metadata=prepared.metadata,
            artifacts=tuple(
                AnalyzerArtifactInput(
                    artifact_id=a.artifact_id,
                    artifact_type=a.artifact_type,
                    format=a.format,
                    content=_ReadOnlyAnalyzerInput(
                        case.registry.with_local_artifact_path(a.artifact_ref, lambda p: p)
                    ),
                )
                for a in prepared.artifacts
            ),
        )
    finally:
        case.cleanup()


@pytest.mark.parametrize(
    "mode,subsampling,progressive",
    [
        ("L", 0, False),
        ("L", 0, True),
        ("RGB", 0, False),
        ("RGB", 1, False),
        ("RGB", 2, False),
        ("RGB", 2, True),
    ],
)
@pytest.mark.parametrize("history", ["single", "aligned", "clipping_challenge"])
def test_real_preprocessing_and_spawned_worker(tmp_path, mode, subsampling, progressive, history):
    rng = np.random.default_rng(21)
    low, high = (0, 256) if history == "clipping_challenge" else (64, 192)
    image = Image.fromarray(rng.integers(low, high, (264, 264, 3), dtype=np.uint8)).convert(mode)
    first = io.BytesIO()
    image.save(
        first,
        format="JPEG",
        quality=90 if history == "single" else 40,
        subsampling=subsampling,
        progressive=progressive,
    )
    data = first.getvalue()
    if history != "single":
        with Image.open(io.BytesIO(data)) as previous:
            second = io.BytesIO()
            previous.save(
                second, format="JPEG", quality=90, subsampling=subsampling, progressive=progressive
            )
            data = second.getvalue()
    with _prepared(tmp_path, data) as request:
        result = _ANALYZER.analyze(request)
        assert result.raw_metrics["median"] == oracle_score(
            oracle_measure(request), "empty_fraction"
        )
        assert result.raw_metrics["decision"] == (
            "positive" if history == "aligned" else "no_signal"
        )
        run = _SpawnedWorkerRunner().run(_worker(request), 10)
        assert run.response is not None
        envelope = json.loads(run.response)
        assert envelope["kind"] == "result"
        assert AnalyzerResult.model_validate(envelope["result"]) == result


@pytest.mark.parametrize("format", ["PNG", "WEBP"])
def test_non_jpeg_uses_normal_not_applicable(tmp_path, format):
    data = io.BytesIO()
    Image.new("RGB", (32, 32)).save(data, format=format)
    with _prepared(tmp_path, data.getvalue()) as request:
        response = json.loads(_execute_worker(_worker(request)))
        assert response["kind"] == "result"
        result = AnalyzerResult.model_validate(response["result"])
        assert result.status is AnalyzerStatus.NOT_APPLICABLE
        assert not result.applicable and not result.candidate_findings
        assert result.score is result.score_name is None


@pytest.mark.parametrize("failure", ["decode", "coefficient_limit", "artifact_budget"])
def test_preprocessing_failure_keeps_framework_semantics(tmp_path, monkeypatch, failure):
    from fakedetector.core._bounded_process import ProcessResult
    from fakedetector.preprocessing._errors import PreprocessingError

    size = (2049, 2048) if failure == "coefficient_limit" else (1024, 1024)
    data = io.BytesIO()
    Image.new("L", size, 128).save(data, format="JPEG")
    if failure == "decode":
        monkeypatch.setattr(
            "fakedetector.preprocessing._media_tools.run_bounded_process",
            lambda *a, **kw: ProcessResult(2, b"", b"private failure"),
        )
    with (
        pytest.raises(PreprocessingError) as caught,
        _prepared(
            tmp_path, data.getvalue(), max_size_mb=1 if failure == "artifact_budget" else None
        ),
    ):
        pytest.fail("preprocessing failure must not reach the analyzer")
    assert caught.value.kind == ("decode" if failure == "decode" else "resource_limit")


def test_large_admitted_jpeg_through_preprocessing(tmp_path):
    data = io.BytesIO()
    Image.new("L", (2048, 2048), 128).save(data, format="JPEG")
    with _prepared(tmp_path, data.getvalue()) as request:
        run = _SpawnedWorkerRunner().run(_worker(request), 10)
        assert run.response is not None
        envelope = json.loads(run.response)
        assert envelope["kind"] == "result"
        assert envelope["result"]["raw_metrics"]["decision"] == "insufficient_evidence"
        assert envelope["result"]["raw_metrics"]["modes"][0]["n"] == 65536
