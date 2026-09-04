"""Bounded FFmpeg operations used only by trusted preprocessing code."""

from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path

from fakedetector.core._bounded_process import (
    ProcessInfrastructureError,
    ProcessTimeoutError,
    run_bounded_process,
)
from fakedetector.preprocessing._errors import PreprocessingError


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
            timeout_seconds=timeout_seconds,
        )

    def spectrogram(
        self,
        source: Path,
        target: Path,
        *,
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
            timeout_seconds=timeout_seconds,
        )

    def sampled_frame(
        self,
        source: Path,
        target: Path,
        *,
        timestamp_seconds: float,
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
            timeout_seconds=timeout_seconds,
        )

    def extracted_audio(
        self,
        source: Path,
        target: Path,
        *,
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
            timeout_seconds=timeout_seconds,
        )

    def _run(
        self,
        source: Path,
        target: Path,
        output_arguments: Sequence[str],
        *,
        phase: str,
        timeout_seconds: float | None,
    ) -> None:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise OSError
        except OSError:
            raise PreprocessingError("artifact_write", phase) from None

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
            str(target.absolute()),
        ]
        effective_timeout = self._effective_timeout(timeout_seconds)
        try:
            result = run_bounded_process(
                arguments,
                cwd=target.parent,
                timeout_seconds=effective_timeout,
            )
        except ProcessTimeoutError:
            raise PreprocessingError("media_tool", f"{phase}_timeout") from None
        except ProcessInfrastructureError as error:
            raise PreprocessingError(
                "infrastructure",
                f"{phase}_process",
                _cleanup_safety_barrier=error._cleanup_safety_barrier,
            ) from None
        if result.return_code != 0:
            raise PreprocessingError("media_tool", phase)

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
