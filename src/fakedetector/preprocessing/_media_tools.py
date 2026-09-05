"""Bounded FFmpeg operations used only by trusted preprocessing code."""

from __future__ import annotations

import math
import os
from collections.abc import Sequence
from pathlib import Path
from time import monotonic
from typing import BinaryIO

from fakedetector._stage5_resources import (
    _GeneratedArtifactBudget,
    _GeneratedArtifactLimitError,
    _GeneratedArtifactWriteError,
)
from fakedetector.core._bounded_process import (
    ProcessInfrastructureError,
    ProcessOutputLimitError,
    ProcessTimeoutError,
    run_bounded_process,
)
from fakedetector.preprocessing._errors import PreprocessingError

_MAX_FLAC_PROGRESS_BYTES = 16 * 1024
_RIFF_UINT32_MAX = (1 << 32) - 1
_FLAC_TOTAL_SAMPLES_MASK = (1 << 36) - 1


class _StreamedContainerError(Exception):
    """Signal invalid output-container bookkeeping without exposing details."""


class _FFmpegPreprocessingTool:
    """Write one prepared representation directly to a controlled target."""

    def __init__(self, *, executable: str, timeout_seconds: float) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        self._executable = executable
        self._timeout_seconds = timeout_seconds

    def normalized_audio(
        self,
        source: Path,
        target: Path,
        *,
        sample_rate_hz: int,
        channels: int,
        artifact_budget: _GeneratedArtifactBudget,
        timeout_seconds: float | None = None,
    ) -> None:
        """Create a signed 16-bit little-endian PCM WAV without rate/channel changes."""
        self._run(
            source,
            target,
            (
                "-map",
                "0:a:0",
                "-vn",
                "-c:a",
                "pcm_s16le",
                "-ar",
                str(sample_rate_hz),
                "-ac",
                str(channels),
                "-f",
                "wav",
            ),
            phase="audio_normalize",
            artifact_budget=artifact_budget,
            timeout_seconds=timeout_seconds,
        )

    def audio_fragment(
        self,
        source: Path,
        target: Path,
        *,
        start_seconds: float,
        duration_seconds: float,
        sample_rate_hz: int,
        channels: int,
        artifact_budget: _GeneratedArtifactBudget,
        timeout_seconds: float | None = None,
    ) -> None:
        """Stream one factual, unpadded interval from a normalized WAV."""
        self._run(
            source,
            target,
            (
                "-ss",
                _timestamp(start_seconds),
                "-t",
                _timestamp(duration_seconds),
                "-map",
                "0:a:0",
                "-vn",
                "-c:a",
                "pcm_s16le",
                "-ar",
                str(sample_rate_hz),
                "-ac",
                str(channels),
                "-f",
                "wav",
            ),
            phase="audio_fragment",
            artifact_budget=artifact_budget,
            timeout_seconds=timeout_seconds,
        )

    def spectrogram(
        self,
        source: Path,
        target: Path,
        *,
        artifact_budget: _GeneratedArtifactBudget,
        timeout_seconds: float | None = None,
    ) -> None:
        """Create one bounded PNG spectrogram from a normalized audio artifact."""
        self._run(
            source,
            target,
            (
                "-lavfi",
                "showspectrumpic=s=640x320:legend=disabled",
                "-frames:v",
                "1",
                "-c:v",
                "png",
                "-f",
                "image2",
            ),
            phase="audio_spectrogram",
            artifact_budget=artifact_budget,
            timeout_seconds=timeout_seconds,
        )

    def sampled_frame(
        self,
        source: Path,
        target: Path,
        *,
        timestamp_seconds: float,
        artifact_budget: _GeneratedArtifactBudget,
        timeout_seconds: float | None = None,
    ) -> None:
        """Decode one representative PNG at a deterministic target timestamp."""
        self._run(
            source,
            target,
            (
                "-ss",
                _timestamp(timestamp_seconds),
                "-map",
                "0:v:0",
                "-frames:v",
                "1",
                "-c:v",
                "png",
                "-f",
                "image2",
            ),
            phase="video_frame",
            artifact_budget=artifact_budget,
            timeout_seconds=timeout_seconds,
        )

    def extracted_audio(
        self,
        source: Path,
        target: Path,
        *,
        artifact_budget: _GeneratedArtifactBudget,
        timeout_seconds: float | None = None,
    ) -> None:
        """Extract the primary video audio stream as lossless FLAC."""
        self._run(
            source,
            target,
            (
                "-map",
                "0:a:0",
                "-vn",
                "-c:a",
                "flac",
                "-f",
                "flac",
            ),
            phase="video_audio",
            artifact_budget=artifact_budget,
            timeout_seconds=timeout_seconds,
        )

    def _run(
        self,
        source: Path,
        target: Path,
        output_arguments: Sequence[str],
        *,
        phase: str,
        artifact_budget: _GeneratedArtifactBudget,
        timeout_seconds: float | None,
    ) -> None:
        arguments = [
            self._executable,
            "-v",
            "error",
            "-nostdin",
            "-xerror",
            "-err_detect",
            "explode",
            "-n",
            "-i",
            str(source.absolute()),
            *output_arguments,
            "pipe:1",
        ]
        effective_timeout = self._effective_timeout(timeout_seconds)
        started_at = monotonic()
        try:
            with artifact_budget.open_output(target) as output:
                result = run_bounded_process(
                    arguments,
                    cwd=target.parent,
                    timeout_seconds=effective_timeout,
                    stdout_limit_bytes=artifact_budget.remaining_bytes,
                    stdout_sink=output,
                )
        except (ProcessOutputLimitError, _GeneratedArtifactLimitError):
            raise PreprocessingError("resource_limit", phase) from None
        except _GeneratedArtifactWriteError:
            raise PreprocessingError("artifact_write", phase) from None
        except ProcessTimeoutError:
            raise PreprocessingError("media_tool", f"{phase}_timeout") from None
        except ProcessInfrastructureError as error:
            if error.phase == "stdout_write":
                raise PreprocessingError("artifact_write", phase) from None
            raise PreprocessingError(
                "infrastructure",
                f"{phase}_process",
                _cleanup_safety_barrier=error._cleanup_safety_barrier,
            ) from None
        if result.return_code != 0:
            raise PreprocessingError("media_tool", phase)
        try:
            if phase in {"audio_normalize", "audio_fragment"}:
                _finalize_streamed_wav(target)
            elif phase == "video_audio":
                remaining_timeout = effective_timeout - (monotonic() - started_at)
                if remaining_timeout <= 0:
                    raise PreprocessingError("media_tool", "video_audio_timeout")
                self._finalize_streamed_flac(
                    target,
                    timeout_seconds=remaining_timeout,
                )
        except _GeneratedArtifactWriteError:
            raise PreprocessingError("artifact_write", phase) from None
        except _StreamedContainerError:
            raise PreprocessingError("media_tool", phase) from None

    def _finalize_streamed_flac(
        self,
        target: Path,
        *,
        timeout_seconds: float,
    ) -> None:
        arguments = [
            self._executable,
            "-v",
            "error",
            "-nostdin",
            "-xerror",
            "-err_detect",
            "explode",
            "-progress",
            "pipe:1",
            "-stats_period",
            "3600",
            "-i",
            str(target.absolute()),
            "-map",
            "0:a:0",
            "-f",
            "null",
            os.devnull,
        ]
        try:
            result = run_bounded_process(
                arguments,
                cwd=target.parent,
                timeout_seconds=timeout_seconds,
                stdout_limit_bytes=_MAX_FLAC_PROGRESS_BYTES,
            )
        except ProcessOutputLimitError:
            raise _StreamedContainerError from None
        except ProcessTimeoutError:
            raise PreprocessingError("media_tool", "video_audio_timeout") from None
        except ProcessInfrastructureError as error:
            raise PreprocessingError(
                "infrastructure",
                "video_audio_process",
                _cleanup_safety_barrier=error._cleanup_safety_barrier,
            ) from None
        if result.return_code != 0 or result.stdout is None:
            raise _StreamedContainerError
        _finalize_streamed_flac(target, result.stdout)

    def _effective_timeout(self, timeout_seconds: float | None) -> float:
        if timeout_seconds is None:
            return self._timeout_seconds
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or not math.isfinite(float(timeout_seconds))
            or timeout_seconds <= 0
        ):
            raise PreprocessingError("invariant", "execution_budget")
        return min(self._timeout_seconds, float(timeout_seconds))


def _timestamp(value: float) -> str:
    return format(value, ".9f").rstrip("0").rstrip(".") or "0"


def _finalize_streamed_wav(target: Path) -> None:
    """Replace non-seekable RIFF sentinels without growing the artifact."""
    try:
        file_size = target.stat().st_size
        if file_size < 20 or file_size - 8 > _RIFF_UINT32_MAX:
            raise _StreamedContainerError
        with target.open("r+b") as stream:
            if stream.read(12) != b"RIFF\xff\xff\xff\xffWAVE":
                raise _StreamedContainerError
            chunk_offset = 12
            while chunk_offset + 8 <= file_size:
                stream.seek(chunk_offset)
                chunk_header = stream.read(8)
                if len(chunk_header) != 8:
                    raise _StreamedContainerError
                chunk_size = int.from_bytes(chunk_header[4:], "little")
                if chunk_header[:4] == b"data":
                    data_size = file_size - chunk_offset - 8
                    if data_size > _RIFF_UINT32_MAX:
                        raise _StreamedContainerError
                    _rewrite_existing(
                        stream,
                        4,
                        (file_size - 8).to_bytes(4, "little"),
                    )
                    _rewrite_existing(
                        stream,
                        chunk_offset + 4,
                        data_size.to_bytes(4, "little"),
                    )
                    stream.flush()
                    return
                chunk_offset += 8 + chunk_size + (chunk_size & 1)
    except OSError:
        raise _GeneratedArtifactWriteError from None
    raise _StreamedContainerError


def _finalize_streamed_flac(target: Path, progress: bytes) -> None:
    """Fill STREAMINFO total samples measured by one bounded decode pass."""
    out_time_us: int | None = None
    completed = False
    for line in progress.splitlines():
        key, separator, value = line.partition(b"=")
        if not separator:
            continue
        if key == b"out_time_us":
            try:
                out_time_us = int(value)
            except ValueError:
                raise _StreamedContainerError from None
        elif key == b"progress" and value == b"end":
            completed = True
    if not completed or out_time_us is None or out_time_us <= 0:
        raise _StreamedContainerError

    try:
        with target.open("r+b") as stream:
            header = stream.read(42)
            if (
                len(header) != 42
                or header[:4] != b"fLaC"
                or header[4] & 0x7F
                or int.from_bytes(header[5:8], "big") != 34
            ):
                raise _StreamedContainerError
            streaminfo = int.from_bytes(header[18:26], "big")
            sample_rate_hz = streaminfo >> 44
            total_samples = (out_time_us * sample_rate_hz + 500_000) // 1_000_000
            if (
                sample_rate_hz <= 0
                or total_samples <= 0
                or total_samples > _FLAC_TOTAL_SAMPLES_MASK
            ):
                raise _StreamedContainerError
            updated = (streaminfo & ~_FLAC_TOTAL_SAMPLES_MASK) | total_samples
            _rewrite_existing(stream, 18, updated.to_bytes(8, "big"))
            stream.flush()
    except OSError:
        raise _GeneratedArtifactWriteError from None


def _rewrite_existing(stream: BinaryIO, offset: int, data: bytes) -> None:
    """Overwrite fixed header bytes and reject a short physical write."""
    stream.seek(offset)
    if stream.write(data) != len(data):
        raise _GeneratedArtifactWriteError
