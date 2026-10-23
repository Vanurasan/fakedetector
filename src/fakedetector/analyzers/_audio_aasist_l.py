"""Opt-in, offline AASIST-L raw response on one bounded native PCM16 prefix."""

from __future__ import annotations

import hashlib
import importlib
import os
import wave
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from fakedetector._filesystem import (
    open_regular_file_for_read,
    require_file_descriptor_identity,
    require_relative_file_target,
)
from fakedetector.analyzers._models import (
    AnalyzerArtifactInput,
    AnalyzerRequest,
    ApplicabilityResult,
)
from fakedetector.analyzers._real_common import _artifacts, _completed_real_result
from fakedetector.domain import AnalyzerResult, AudioTechnicalParameters, MediaType

_PROFILE = "AASIST-L-PCM16-FIRST-1"
_MODEL_REVISION = "357e022c44a1aa926097e18c1457bde3873ed8bf"
_MODEL_SHA256 = "f43f0a638b52846f5d0e630c0a738d10e9306325945127c6f8662d559585f218"
_MODEL_BYTES = 766114
_INPUT_SAMPLES = 64600
_MIN_OBSERVED_SAMPLES = 1600
_RUNTIME_VERSION = "1.31.0"
_LIMITATION = (
    "Out-of-domain, uncalibrated model response; speech presence is unverified. "
    "Logits are not probabilities, confidence, or a fake/real verdict. "
    "Music, noise, multiple speakers, initial silence and attacks after the first window "
    "are limitations. Cyclic repetition adds no observed evidence."
)


class AudioAasistLSettings(BaseModel):
    """The sole opt-in setting; disabled registration requires no runtime or asset."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    model_path: str | None = Field(default=None, min_length=1, max_length=4096, repr=False)


class AudioAasistLMeasurementAnalyzer:
    analyzer_id: ClassVar[str] = "audio_aasist_l_measurement"
    analyzer_name: ClassVar[str] = "AASIST-L neural measurement"
    analyzer_version: ClassVar[str] = "1.0.0"
    group: ClassVar[str] = "audio"
    supported_media_types: ClassVar[frozenset[MediaType]] = frozenset({MediaType.AUDIO})

    def check_applicability(self, request: AnalyzerRequest) -> ApplicabilityResult:
        facts = request.file_facts.technical_parameters
        if request.media_type is not MediaType.AUDIO or not isinstance(
            facts, AudioTechnicalParameters
        ):
            return ApplicabilityResult(False, "media_type")
        if facts.sample_rate_hz != 16000 or facts.channels != 1:
            return ApplicabilityResult(False, "native_mono_16000_required")
        artifact = _normalized_artifact(request)
        with artifact.content.open_for_read() as stream, wave.open(stream, "rb") as wav:
            _require_pcm16(wav)
            if wav.getframerate() != 16000 or wav.getnchannels() != 1:
                return ApplicabilityResult(False, "wav_mono_16000_required")
        return ApplicabilityResult(True)

    def analyze(self, request: AnalyzerRequest) -> AnalyzerResult:
        if not isinstance(request.settings, AudioAasistLSettings):
            raise TypeError("unexpected AASIST-L settings")
        artifact = _normalized_artifact(request)
        with artifact.content.open_for_read() as stream, wave.open(stream, "rb") as wav:
            _require_pcm16(wav)
            if wav.getframerate() != 16000 or wav.getnchannels() != 1:
                raise ValueError("inconsistent canonical audio parameters")
            source_samples = wav.getnframes()
            observed = min(source_samples, _INPUT_SAMPLES)
            pcm = wav.readframes(observed)
            if len(pcm) != observed * 2:
                raise ValueError("incomplete canonical PCM prefix")

        insufficient = observed < _MIN_OBSERVED_SAMPLES or not any(pcm)
        repeated = not insufficient and observed < _INPUT_SAMPLES
        metrics: dict[str, JsonValue] = {
            "method": "AASIST-L",
            "profile": _PROFILE,
            "model_name": "SpeechAntiSpoofingBenchmarks/AASIST-L",
            "model_version": _MODEL_REVISION,
            "model_revision": _MODEL_REVISION,
            "model_sha256": _MODEL_SHA256,
            "input_representation": "normalized_audio_pcm16_wav",
            "source_sample_rate_hz": 16000,
            "source_channels": 1,
            "source_samples": source_samples,
            "observed_samples": observed,
            "used_samples": 0 if insufficient else observed,
            "input_samples": 0 if insufficient else _INPUT_SAMPLES,
            "window_start_sample": 0,
            "window_end_sample": observed,
            "coverage_ratio": observed / source_samples if source_samples else 0.0,
            "coverage_basis": "observed_prefix_over_normalized_wav_header_frames",
            "padded": repeated,
            "zero_padded": False,
            "repeated": repeated,
            "repeated_samples": _INPUT_SAMPLES - observed if repeated else 0,
            "truncated": source_samples > _INPUT_SAMPLES,
            "speech_presence": "unverified",
            "state": "insufficient_evidence" if insufficient else "measured",
            "insufficiency_reason": (
                "too_short" if observed < _MIN_OBSERVED_SAMPLES else "digital_silence"
            )
            if insufficient
            else None,
            "raw_logits": None,
            "bona_fide_logit": None,
            "limitations": _LIMITATION,
        }
        if not insufficient:
            # These imports, model I/O and native initialization occur only in execution.
            import numpy as np

            waveform = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / np.float32(32768)
            if repeated:
                waveform = np.tile(waveform, _INPUT_SAMPLES // observed + 1)[:_INPUT_SAMPLES]
            model = _read_model_bytes(request.settings.model_path)
            runtime = importlib.import_module("onnxruntime")
            if runtime.__version__ != _RUNTIME_VERSION:
                raise ValueError("unsupported optional runtime version")
            options = runtime.SessionOptions()
            options.intra_op_num_threads = 1
            options.inter_op_num_threads = 1
            options.execution_mode = runtime.ExecutionMode.ORT_SEQUENTIAL
            options.log_severity_level = 4
            session = runtime.InferenceSession(
                model, sess_options=options, providers=["CPUExecutionProvider"]
            )
            session.disable_fallback()
            if session.get_providers() != ["CPUExecutionProvider"]:
                raise ValueError("unexpected execution provider")
            outputs = session.run(["logits"], {"wav": waveform.reshape(1, _INPUT_SAMPLES)})
            if (
                len(outputs) != 1
                or not isinstance(outputs[0], np.ndarray)
                or outputs[0].dtype != np.float32
                or outputs[0].shape != (1, 2)
                or not np.isfinite(outputs[0]).all()
            ):
                raise ValueError("invalid AASIST-L output")
            metrics["raw_logits"] = [float(outputs[0][0, 0]), float(outputs[0][0, 1])]
            metrics["bona_fide_logit"] = float(outputs[0][0, 1])

        result = _completed_real_result(
            analyzer_id=self.analyzer_id,
            analyzer_version=self.analyzer_version,
            group=self.group,
            request=request,
            summary=(
                "Experimental AASIST-L measurement: insufficient evidence. "
                if insufficient
                else "Experimental AASIST-L raw logits measured. "
            )
            + _LIMITATION,
            raw_metrics=metrics,
        )
        return result.model_copy(update={"warnings": [_LIMITATION]})


def _normalized_artifact(request: AnalyzerRequest) -> AnalyzerArtifactInput:
    artifacts = _artifacts(request, "normalized_audio")
    if len(artifacts) != 1 or artifacts[0].format.casefold() != "wav":
        raise ValueError("one canonical WAV artifact is required")
    return artifacts[0]


def _require_pcm16(wav: wave.Wave_read) -> None:
    if wav.getsampwidth() != 2 or wav.getcomptype() != "NONE":
        raise ValueError("uncompressed signed PCM16 is required")


def _read_model_bytes(configured: str | None) -> bytes:
    if configured is None:
        raise ValueError("offline model asset is not configured")
    path = Path(configured)
    if (
        not path.is_absolute()
        or path.anchor.startswith("\\\\")
        or path.suffix.casefold() != ".onnx"
        or any(
            part in {".", ".."} or ":" in part or part.endswith((".", " "))
            for part in path.parts[1:]
        )
    ):
        raise ValueError("unsafe offline model location")
    package = Path(__file__).absolute().parents[1]
    source_root = package.parent.parent if package.parent.name == "src" else package
    if path.is_relative_to(source_root):
        raise ValueError("model asset must be outside the source/package tree")
    root = Path(path.anchor)
    require_relative_file_target(root, path, missing_ok=False)
    with open_regular_file_for_read(path) as stream:
        info = os.fstat(stream.fileno())
        if info.st_size != _MODEL_BYTES or info.st_nlink != 1:
            raise ValueError("invalid offline model file")
        payload = stream.read(_MODEL_BYTES + 1)
        require_file_descriptor_identity(path, stream.fileno())
        require_relative_file_target(root, path, missing_ok=False)
    if len(payload) != _MODEL_BYTES or hashlib.sha256(payload).hexdigest() != _MODEL_SHA256:
        raise ValueError("offline model integrity mismatch")
    return payload
