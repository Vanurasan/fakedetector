"""Synthetic source-bound inputs for diploma analyzer contract tests."""

import json

import numpy as np

from fakedetector.analyzers._catalog import _resolve_runtime_analyzer_definition
from fakedetector.analyzers._experimental_common import _ExperimentalSettings
from fakedetector.analyzers._models import (
    AnalyzerArtifactInput,
    AnalyzerRequest,
    _AnalyzerFileFacts,
    _ReadOnlyAnalyzerInput,
)
from fakedetector.analyzers._orchestrator import _plain_json_value
from fakedetector.analyzers._transport import _WorkerArtifact, _WorkerRequest
from fakedetector.preprocessing._media_tools import stft_batches
from fakedetector.preprocessing._models import (
    AudioPrecisionFacts,
    AudioWindowDescriptor,
    ForensicManifest,
    ForensicRepresentation,
    IndexRange,
    NumericArtifact,
    RepresentationProvenance,
    SpectralWindowDescriptor,
)


def numeric(tmp_path, artifact_id, values):
    path = tmp_path / artifact_id
    path.write_bytes(values.tobytes())
    descriptor = NumericArtifact(
        artifact_id=artifact_id, dtype=values.dtype.str, shape=values.shape
    )
    artifact = AnalyzerArtifactInput(
        artifact_id=artifact_id,
        artifact_type="numeric",
        format="forensic_raw",
        content=_ReadOnlyAnalyzerInput(path),
    )
    return descriptor, artifact


def request_for(tmp_path, descriptor, representations=(), artifacts=()):
    metadata = {}
    if representations:
        manifest = ForensicManifest(
            source_sha256=descriptor.sha256,
            media_type=descriptor.media_type,
            representations=tuple(representations),
        )
        metadata["forensic"] = manifest.to_metadata()
    return AnalyzerRequest(
        analysis_id="a" * 32,
        media_type=descriptor.media_type,
        file_facts=_AnalyzerFileFacts.from_validated_file(descriptor),
        source=_ReadOnlyAnalyzerInput(tmp_path / "source_must_not_be_read"),
        settings=_ExperimentalSettings(),
        timeout_seconds=15,
        artifacts=tuple(artifacts),
        metadata=metadata,
    )


def audio_request(tmp_path, samples, *, rate=8000, magnitude=None, start=0, pts=-500):
    from test_preprocessing import _audio_descriptor

    samples = np.asarray(samples)
    if samples.ndim == 1:
        samples = samples[:, None]
    samples = samples.astype("<i4" if samples.dtype.kind in "iu" else "<f8")
    samples = np.frombuffer(samples.tobytes(), dtype=samples.dtype).reshape(samples.shape)
    precision = AudioPrecisionFacts(
        stream_index=0,
        codec="pcm_s32le" if samples.dtype.kind == "i" else "pcm_f64le",
        source_bits=32 if samples.dtype.kind == "i" else None,
        decoder_format="s32" if samples.dtype.kind == "i" else "dbl",
        sample_rate=rate,
        channels=samples.shape[1],
    )
    provenance = RepresentationProvenance(
        producer="ffmpeg_audio",
        producer_version="1",
        profile="precision_windows",
        profile_version="1",
    )
    data, artifact = numeric(tmp_path, "samples", samples)
    window = AudioWindowDescriptor(
        stream_index=0,
        samples=IndexRange(start=start, stop=start + len(samples)),
        first_sample_pts=pts,
        data=data,
    )
    representations = [
        ForensicRepresentation(provenance=provenance, facts=precision),
        ForensicRepresentation(provenance=provenance, facts=window),
    ]
    artifacts = [artifact]
    if len(samples) >= 4096:
        if magnitude is None:
            magnitude = np.concatenate(
                [
                    b.values
                    for b in stft_batches(
                        samples,
                        sample_rate=rate,
                        n_fft=4096,
                        hop=1024,
                        batch_size=16,
                    )
                ]
            )
        spectral, artifact = numeric(tmp_path, "spectral", magnitude.astype("<f8"))
        artifacts.append(artifact)
        representations.append(
            ForensicRepresentation(
                provenance=RepresentationProvenance(
                    producer="numpy_stft",
                    producer_version="1",
                    profile="hann4096_hop1024",
                    profile_version="1",
                ),
                facts=SpectralWindowDescriptor(
                    samples_artifact_id=data.artifact_id,
                    frames=IndexRange(start=0, stop=len(magnitude)),
                    n_fft=4096,
                    hop=1024,
                    window="hann",
                    scaling="magnitude",
                    data=spectral,
                ),
            )
        )
    return request_for(
        tmp_path,
        _audio_descriptor(
            duration_seconds=len(samples) / rate,
            sample_rate_hz=rate,
            channels=samples.shape[1],
        ),
        representations,
        artifacts,
    )


def worker_request(analyzer, request):
    definition = _resolve_runtime_analyzer_definition(analyzer.analyzer_id)
    assert definition is not None
    return _WorkerRequest(
        worker_key=definition.worker_key,
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
                start_time_seconds=a.start_time_seconds,
                end_time_seconds=a.end_time_seconds,
                frame_index=a.frame_index,
            )
            for a in request.artifacts
        ),
        metadata_json=json.dumps(_plain_json_value(request.metadata)),
        warnings=(),
        settings_json="{}",
        timeout_seconds=15,
    )


def image_request(tmp_path, pixels):
    from PIL import Image
    from test_preprocessing import _image_descriptor

    path = tmp_path / "normalized.png"
    Image.fromarray(pixels).save(path)
    artifact = AnalyzerArtifactInput(
        artifact_id="normalized_image",
        artifact_type="normalized_image",
        format="png",
        content=_ReadOnlyAnalyzerInput(path),
    )
    return request_for(
        tmp_path,
        _image_descriptor(
            width=pixels.shape[1],
            height=pixels.shape[0],
            image_format="PNG",
            color_mode="RGBA" if pixels.shape[2] == 4 else "RGB",
        ),
        artifacts=[artifact],
    )


def video_request(tmp_path, windows, *, ticks=None, masks=None, native=None):
    from test_preprocessing import _video_descriptor

    from fakedetector.preprocessing._models import (
        DenseVideoWindowDescriptor,
        StreamTimingFacts,
        TimeBase,
        TimingInterval,
        TimingRecordsDescriptor,
    )

    height, width = windows[0].shape[1:3]
    native_width, native_height = native or (width, height)
    base = TimeBase(numerator=1, denominator=1000)
    stream = StreamTimingFacts(
        stream_index=0,
        stream_kind="video",
        time_base=base,
        start_tick=0,
        duration_ticks=20000,
        native_width=native_width,
        native_height=native_height,
    )
    provenance = RepresentationProvenance(
        producer="ffprobe", producer_version="1", profile="timing_records", profile_version="1"
    )
    dense_provenance = RepresentationProvenance(
        producer="ffmpeg_dense", producer_version="1", profile="rgb24_bilinear", profile_version="1"
    )
    representations = [ForensicRepresentation(provenance=provenance, facts=stream)]
    artifacts = []
    for region, pixels in enumerate(windows):
        clock = np.asarray(
            ticks[region]
            if ticks is not None
            else [region * 5000 + i * 40 for i in range(len(pixels))],
            dtype="<i8",
        )
        table = np.zeros((len(pixels), 9), dtype="<i8")
        table[:, 0] = clock
        table[:, 2] = 40
        table[:, 3] = np.arange(len(pixels))
        table[:, 4] = masks[region] if masks is not None else 5
        observed = clock[(table[:, 4] & 1) != 0]
        table[(table[:, 4] & 1) == 0, 0] = 0
        data, artifact = numeric(tmp_path, f"timing_{region}", table)
        artifacts.append(artifact)
        first, last = int(observed[0]), int(observed[-1])
        timing = TimingRecordsDescriptor(
            purpose="dense",
            stream_index=0,
            region=region,
            record_kind="frame",
            first_tick=first,
            last_tick=last,
            requested=TimingInterval(start=first, stop=last + 40),
            coverage="envelope" if np.all(table[:, 4] & 1) else "unknown",
            stop_reason="dense_limits_or_eof",
            decode_operation_id=f"operation_{region}",
            data=data,
        )
        pixel_data, artifact = numeric(tmp_path, f"pixels_{region}", pixels.astype("u1"))
        artifacts.append(artifact)
        dense = DenseVideoWindowDescriptor(
            timing_artifact_id=data.artifact_id,
            decode_operation_id=timing.decode_operation_id,
            native_width=native_width,
            native_height=native_height,
            pixels=pixel_data,
        )
        representations.extend(
            [
                ForensicRepresentation(provenance=dense_provenance, facts=timing),
                ForensicRepresentation(provenance=dense_provenance, facts=dense),
            ]
        )
    return request_for(
        tmp_path,
        _video_descriptor(
            duration_seconds=20, width=native_width, height=native_height, fps=25, has_audio=False
        ),
        representations,
        artifacts,
    )
