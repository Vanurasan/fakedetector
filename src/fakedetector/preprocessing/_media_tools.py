"""Bounded FFmpeg operations used only by trusted preprocessing code."""

from __future__ import annotations

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
        )

    def spectrogram(self, source: Path, target: Path) -> None:
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
        )

    def sampled_frame(self, source: Path, target: Path, *, timestamp_seconds: float) -> None:
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
        )

    def extracted_audio(self, source: Path, target: Path) -> None:
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
        )

    def _run(
        self,
        source: Path,
        target: Path,
        output_arguments: Sequence[str],
        *,
        phase: str,
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
        try:
            result = run_bounded_process(
                arguments,
                cwd=target.parent,
                timeout_seconds=self._timeout_seconds,
            )
        except ProcessTimeoutError:
            raise PreprocessingError("media_tool", f"{phase}_timeout") from None
        except ProcessInfrastructureError:
            raise PreprocessingError("infrastructure", f"{phase}_process") from None
        if result.return_code != 0:
            raise PreprocessingError("media_tool", phase)


def _timestamp(value: float) -> str:
    return format(value, ".9f").rstrip("0").rstrip(".") or "0"
