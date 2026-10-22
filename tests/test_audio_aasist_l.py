"""Bounded native PCM, pinned bytes, lazy runtime and worker/lifecycle contracts."""

import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import wave
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml
from fastapi.testclient import TestClient
from support.diploma_inputs import request_for, worker_request
from test_analyzer_worker import _FakeBackend, _FakeProcess
from test_preprocessing import _audio_descriptor
from test_stage9_e2e import _post_api, _wait_for_result

from fakedetector.analyzers import _audio_aasist_l as aasist
from fakedetector.analyzers._catalog import (
    _AnalyzerMaturity,
    _resolve_runtime_analyzer_definition,
    _runtime_analyzer_registrations,
)
from fakedetector.analyzers._models import AnalyzerArtifactInput, _ReadOnlyAnalyzerInput
from fakedetector.analyzers._registry import AnalyzerRegistry
from fakedetector.analyzers._transport import _serialize_analyzer_result
from fakedetector.analyzers._worker import _execute_worker, _SpawnedWorkerRunner, _WorkerRunKind
from fakedetector.app import create_app
from fakedetector.config.models import AppConfig
from fakedetector.domain import AnalyzerResult, MediaType

ANALYZER = aasist.AudioAasistLMeasurementAnalyzer()


def _wav(samples, rate=16000, channels=1, width=2):
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(channels)
        wav.setframerate(rate)
        wav.setsampwidth(width)
        wav.writeframes(np.asarray(samples, dtype="<i2").tobytes())
    return output.getvalue()


def _request(tmp_path, samples=None, *, rate=16000, channels=1, width=2, model_path=None):
    if samples is None:
        samples = np.full(64600, 1000, dtype="<i2")
    path = tmp_path / "canonical.wav"
    path.write_bytes(_wav(samples, rate, channels, width))
    artifact = AnalyzerArtifactInput(
        artifact_id="audio_normalized",
        artifact_type="normalized_audio",
        content=_ReadOnlyAnalyzerInput(path),
        format="wav",
    )
    descriptor = _audio_descriptor(
        duration_seconds=max(0.001, len(samples) / rate / channels),
        sample_rate_hz=rate,
        channels=channels,
    )
    request = request_for(tmp_path, descriptor, artifacts=[artifact])
    return replace(request, settings=aasist.AudioAasistLSettings(model_path=model_path))


def _transport(request):
    return replace(
        worker_request(ANALYZER, request), settings_json=request.settings.model_dump_json()
    )


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    payload = b"checked-model-bytes"
    model = tmp_path / "model.onnx"
    model.write_bytes(payload)
    monkeypatch.setattr(aasist, "_MODEL_BYTES", len(payload))
    monkeypatch.setattr(aasist, "_MODEL_SHA256", hashlib.sha256(payload).hexdigest())
    calls = []
    behavior = SimpleNamespace(output=np.array([[-2.0, 3.0]], dtype="f4"), fail=None)

    class Session:
        def __init__(self, data, *, sess_options, providers):
            assert data == payload and isinstance(data, bytes)
            assert sess_options.intra_op_num_threads == sess_options.inter_op_num_threads == 1
            assert sess_options.execution_mode == "sequential"
            assert providers == ["CPUExecutionProvider"]
            calls.append("session")
            if behavior.fail == "load":
                raise RuntimeError("PRIVATE model load path")
            # A replacement after validation cannot change the bytes given to ORT.
            model.write_bytes(b"replaced")

        def disable_fallback(self):
            calls.append("disable_fallback")

        def get_providers(self):
            return ["CPUExecutionProvider"]

        def run(self, names, inputs):
            assert names == ["logits"]
            waveform = inputs["wav"]
            assert waveform.dtype == np.float32 and waveform.shape == (1, 64600)
            calls.append(waveform.copy())
            if behavior.fail == "inference":
                raise RuntimeError("PRIVATE inference path")
            return [behavior.output]

    fake = SimpleNamespace(
        __version__="1.31.0",
        SessionOptions=SimpleNamespace,
        ExecutionMode=SimpleNamespace(ORT_SEQUENTIAL="sequential"),
        InferenceSession=Session,
    )
    original_import = aasist.importlib.import_module
    monkeypatch.setattr(
        aasist.importlib,
        "import_module",
        lambda name, *args: fake if name == "onnxruntime" else original_import(name, *args),
    )
    return str(model), calls, behavior


def test_closed_catalog_default_settings_and_no_ml_startup(tmp_path):
    definition = _resolve_runtime_analyzer_definition(ANALYZER.analyzer_id)
    assert definition.maturity is _AnalyzerMaturity.EXPERIMENTAL
    assert definition.settings_model().model_dump() == {"model_path": None}
    assert not definition.candidate_finding_types and definition.max_candidate_findings == 0
    assert not definition.preprocessing_requirements.forensic
    for filename in ("config.example.yaml", "config.diploma.yaml"):
        raw = yaml.safe_load(Path("config", filename).read_text(encoding="utf-8"))
        config = AppConfig.model_validate(raw)
        registry = AnalyzerRegistry(config, _runtime_analyzer_registrations())
        assert ANALYZER.analyzer_id not in registry.active_analyzer_ids(MediaType.AUDIO)
    code = """
import builtins, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'onnxruntime', 'torch', 'onnx'}:
        raise AssertionError('heavy import on startup')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from fakedetector.analyzers._catalog import _runtime_analyzer_registrations
from fakedetector.analyzers._registry import AnalyzerRegistry
from fakedetector.config.models import AppConfig
from pathlib import Path
import yaml
for entry in _runtime_analyzer_registrations():
    entry.settings_model()
raw = yaml.safe_load(Path('config/config.example.yaml').read_text('utf-8'))
config = AppConfig.model_validate(raw)
AnalyzerRegistry(config, _runtime_analyzer_registrations())
assert 'onnxruntime' not in sys.modules
"""
    completed = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=15)
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")


@pytest.mark.parametrize("rate,channels", [(8000, 1), (48000, 1), (16000, 2)])
def test_native_and_actual_wav_applicability(tmp_path, rate, channels):
    request = _request(tmp_path, rate=rate, channels=channels)
    assert not ANALYZER.check_applicability(request).applicable
    native = _request(tmp_path)
    native.artifacts[0].content._local_path.write_bytes(_wav([10] * 3200, rate, channels))
    assert not ANALYZER.check_applicability(native).applicable


@pytest.mark.parametrize("count", [1600, 64599, 64600, 64601, 130000])
def test_scaling_repeat_truncation_and_bounded_serialization(tmp_path, runtime, count):
    model, calls, _ = runtime
    samples = np.resize(np.array([-32768, -1, 0, 32767], dtype="<i2"), count)
    request = _request(tmp_path, samples, model_path=model)
    assert ANALYZER.check_applicability(request).applicable
    envelope = json.loads(_execute_worker(_transport(request)))
    assert envelope["kind"] == "result"
    result = AnalyzerResult.model_validate(envelope["result"])
    assert len(calls) == 3 and calls[0:2] == ["session", "disable_fallback"]
    expected = np.resize(samples[:64600], 64600).astype("f4") / np.float32(32768)
    np.testing.assert_array_equal(calls[2][0], expected)
    metrics = result.raw_metrics
    assert metrics["observed_samples"] == metrics["used_samples"] == min(count, 64600)
    assert metrics["source_samples"] == count and metrics["input_samples"] == 64600
    assert metrics["truncated"] == (count > 64600)
    assert metrics["repeated"] == metrics["padded"] == (count < 64600)
    assert metrics["coverage_ratio"] == min(count, 64600) / count
    assert metrics["raw_logits"] == [-2, 3] and metrics["bona_fide_logit"] == 3
    assert metrics["speech_presence"] == "unverified" and metrics["state"] == "measured"
    assert result.score is result.score_name is None and result.candidate_findings == []
    serialized = _serialize_analyzer_result(result)
    assert len(serialized) < 4096 and str(tmp_path).encode() not in serialized
    assert "uncalibrated" in result.summary and result.warnings


@pytest.mark.parametrize("count,value", [(0, 0), (1, 100), (1599, 100), (1600, 0), (80000, 0)])
def test_insufficiency_does_not_import_or_emit_logits(tmp_path, monkeypatch, count, value):
    def forbidden(*args):
        pytest.fail("insufficient signal must not load a model/runtime")

    monkeypatch.setattr(aasist, "_read_model_bytes", forbidden)
    request = _request(tmp_path, np.full(count, value, dtype="<i2"))
    result = ANALYZER.analyze(request)
    assert result.raw_metrics["state"] == "insufficient_evidence"
    assert result.raw_metrics["raw_logits"] is result.raw_metrics["bona_fide_logit"] is None
    assert result.raw_metrics["used_samples"] == result.raw_metrics["input_samples"] == 0


@pytest.mark.parametrize("mode", ["missing", "hash", "size", "runtime", "load", "inference"])
def test_asset_and_runtime_failures_are_safe_worker_errors(tmp_path, runtime, monkeypatch, mode):
    model, calls, behavior = runtime
    request = _request(tmp_path, model_path=model)
    if mode == "missing":
        request = replace(request, settings=aasist.AudioAasistLSettings())
    elif mode == "hash":
        Path(model).write_bytes(b"x" * len(Path(model).read_bytes()))
    elif mode == "size":
        Path(model).write_bytes(b"x")
    elif mode == "runtime":

        def missing(*args):
            raise ModuleNotFoundError("PRIVATE optional runtime path")

        monkeypatch.setattr(aasist.importlib, "import_module", missing)
    else:
        behavior.fail = mode
    response = _execute_worker(_transport(request))
    assert json.loads(response) == {"kind": "analyzer_error"}
    assert b"PRIVATE" not in response and str(tmp_path).encode() not in response
    if mode in {"missing", "hash", "size", "runtime"}:
        assert calls == []


@pytest.mark.parametrize(
    "output",
    [
        np.array([[np.nan, 0]], dtype="f4"),
        np.array([[0, np.inf]], dtype="f4"),
        np.zeros((2, 2), dtype="f4"),
        np.zeros(2, dtype="f4"),
        np.zeros((1, 2), dtype="f8"),
        [[0, 1]],
    ],
)
def test_invalid_output_is_error(tmp_path, runtime, output):
    model, _, behavior = runtime
    behavior.output = output
    assert json.loads(_execute_worker(_transport(_request(tmp_path, model_path=model)))) == {
        "kind": "analyzer_error"
    }


@pytest.mark.parametrize("kind", ["width", "encoding", "truncated", "missing", "header"])
def test_corrupt_controlled_artifact_preserves_failure_boundary(tmp_path, kind):
    request = _request(tmp_path, width=1 if kind == "width" else 2)
    path = request.artifacts[0].content._local_path
    if kind == "missing":
        path.rename(tmp_path / "moved.wav")
    elif kind == "truncated":
        path.write_bytes(path.read_bytes()[:-2])
    elif kind == "encoding":
        raw = bytearray(path.read_bytes())
        raw[20:22] = b"\x03\x00"  # IEEE float is not signed PCM16.
        path.write_bytes(raw)
    elif kind == "header":
        path.write_bytes(b"not a WAV")
    response = json.loads(_execute_worker(_transport(request)))
    assert response == {"kind": "worker_error" if kind == "missing" else "analyzer_error"}


def test_asset_location_links_and_identity(tmp_path, runtime):
    model, _, _ = runtime
    assert aasist._read_model_bytes(model) == b"checked-model-bytes"
    for path in [None, "relative.onnx", str(Path.cwd() / "model.onnx"), str(tmp_path)]:
        with pytest.raises((ValueError, OSError)):
            aasist._read_model_bytes(path)
    link = tmp_path / "hard.onnx"
    os.link(model, link)
    with pytest.raises(ValueError):
        aasist._read_model_bytes(model)


def test_spawned_missing_model_single_invocation_and_reap(tmp_path, real_worker_processes):
    run = _SpawnedWorkerRunner().run(_transport(_request(tmp_path)), timeout_seconds=15)
    assert run.kind is _WorkerRunKind.RESPONSE
    assert json.loads(run.response) == {"kind": "analyzer_error"}
    assert len(real_worker_processes) == 1 and real_worker_processes[0]._closed


@pytest.mark.parametrize("terminate_stops", [True, False])
def test_aasist_deadline_uses_existing_terminate_kill_reap(tmp_path, terminate_stops):
    class Backend(_FakeBackend):
        def create_process(self, *, target, args):
            assert args[1].worker_key == "stage13.audio_aasist_l_measurement.v1"
            assert args[2] is None
            self.process_creations += 1
            return self.process

    process = _FakeProcess(terminate_stops=terminate_stops, kill_stops=True)
    backend = Backend(process)
    run = _SpawnedWorkerRunner(backend=backend).run(_transport(_request(tmp_path)), 0.01)
    assert run.kind is _WorkerRunKind.TIMEOUT
    assert backend.process_creations == 1 and process.terminated
    assert process.killed == (not terminate_stops)
    assert not process.alive and process.closed and process.join_timeouts


def test_real_aasist_timeout_reaps_before_return(tmp_path, real_worker_processes):
    run = _SpawnedWorkerRunner().run(_transport(_request(tmp_path)), timeout_seconds=0.001)
    assert run.kind is _WorkerRunKind.TIMEOUT
    assert len(real_worker_processes) == 1 and real_worker_processes[0]._closed


def test_failure_persists_safe_error_and_cleans_controlled_artifacts(
    tmp_path, real_worker_processes, real_subprocesses
):
    raw = yaml.safe_load(Path("config/config.diploma.yaml").read_text(encoding="utf-8"))
    raw["temporary_storage"]["root_path"] = str(tmp_path / "temp")
    raw["result"]["directory"] = str(tmp_path / "results")
    raw["analyzers"]["audio"]["enabled"] = [ANALYZER.analyzer_id]
    config = AppConfig.model_validate(raw)
    with TestClient(create_app(config)) as client:
        response = _post_api(client, "audio.wav", "audio/wav", _wav(np.ones(64600)))
        assert response.status_code == 202
        result = _wait_for_result(client, response.json()["analysis_id"])
    assert result["analyzers"][0]["status"] == "error"
    assert result["cleanup"]["status"] == "completed"
    assert not (tmp_path / "temp" / result["analysis_id"]).exists()
    assert str(tmp_path) not in json.dumps(result)
    assert len(real_worker_processes) == 1 and real_worker_processes[0]._closed


def test_real_pinned_model_spawned_smoke(tmp_path, real_worker_processes):
    model = os.environ.get("AASIST_L_TEST_MODEL_PATH")
    if not model or importlib.util.find_spec("onnxruntime") is None:
        pytest.skip("opt-in pinned asset and optional runtime required")
    # Generated execution fixture; this is no speech/accuracy assertion.
    samples = np.resize(np.array([-1000, 1000], dtype="<i2"), 64600)
    run = _SpawnedWorkerRunner().run(
        _transport(_request(tmp_path, samples, model_path=model)), timeout_seconds=20
    )
    result = json.loads(run.response)["result"]
    assert result["status"] == "completed" and result["raw_metrics"]["state"] == "measured"
    assert len(result["raw_metrics"]["raw_logits"]) == 2
    assert result["raw_metrics"]["model_sha256"] == aasist._MODEL_SHA256
    assert result["score"] is None and not result["candidate_findings"]
    assert len(real_worker_processes) == 1 and real_worker_processes[0]._closed
