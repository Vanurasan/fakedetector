"""Narrow, bounded FFmpeg/ffprobe boundary for primary media validation."""

from __future__ import annotations

import json
import math
import subprocess
import threading
from contextlib import suppress
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

_PROBE_SIZE_BYTES = 5 * 1024 * 1024
_ANALYZE_DURATION_MICROSECONDS = 5_000_000
_MAX_PROBE_OUTPUT_BYTES = 64 * 1024
_BOUNDED_DECODE_SECONDS = 1
_BOUNDED_VIDEO_FRAMES = 3


class MediaToolSystemError(Exception):
    """Safe infrastructure failure that must not classify a file as invalid."""

    def __init__(self, phase: str) -> None:
        super().__init__("Media validation infrastructure failed.")
        self.phase = phase


class MediaRejectedError(Exception):
    """Expected failure to probe or decode one untrusted media input."""

    def __init__(self, phase: str) -> None:
        super().__init__("Media could not be safely read.")
        self.phase = phase


@dataclass(frozen=True, slots=True)
class AudioProbe:
    """Required and optional scalar audio properties from a controlled probe."""

    duration_seconds: float
    sample_rate_hz: int
    channels: int
    codec: str
    bitrate_bps: int | None


@dataclass(frozen=True, slots=True)
class VideoProbe:
    """Required and optional scalar video properties from a controlled probe."""

    duration_seconds: float
    video_codec: str
    audio_codec: str | None
    width: int
    height: int
    fps: float
    bitrate_bps: int | None
    has_audio: bool


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """Minimal parsed ffprobe result used for container and stream validation."""

    format_names: frozenset[str]
    format_duration_seconds: float | None
    format_bitrate_bps: int | None
    audio_streams: tuple[dict[str, Any], ...]
    video_streams: tuple[dict[str, Any], ...]


class FFmpegMediaInspector:
    """Probe and bounded-decode controlled local audio/video sources."""

    def __init__(
        self,
        *,
        ffprobe_executable: str = "ffprobe",
        ffmpeg_executable: str = "ffmpeg",
        timeout_seconds: float = 15.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        self._ffprobe_executable = ffprobe_executable
        self._ffmpeg_executable = ffmpeg_executable
        self._timeout_seconds = timeout_seconds

    def probe(self, source_path: Path) -> ProbeResult:
        """Return only fields required by the Stage 3 technical-parameter models."""
        controlled_source_path = source_path.absolute()
        arguments = [
            self._ffprobe_executable,
            "-v",
            "error",
            "-probesize",
            str(_PROBE_SIZE_BYTES),
            "-analyzeduration",
            str(_ANALYZE_DURATION_MICROSECONDS),
            "-show_entries",
            (
                "format=format_name,duration,bit_rate:"
                "stream=codec_type,codec_name,sample_rate,channels,duration,bit_rate,"
                "width,height,avg_frame_rate,r_frame_rate,disposition"
            ),
            "-of",
            "json",
            str(controlled_source_path),
        ]
        output = self._run_probe(arguments, cwd=controlled_source_path.parent)
        try:
            payload = json.loads(output.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise MediaToolSystemError("ffprobe_output") from None
        return _parse_probe_payload(payload)

    def decode_audio(self, source_path: Path) -> None:
        """Decode at most the first second of the primary audio stream."""
        controlled_source_path = source_path.absolute()
        self._run_decode(
            [
                self._ffmpeg_executable,
                "-v",
                "error",
                "-nostdin",
                "-xerror",
                "-err_detect",
                "explode",
                "-probesize",
                str(_PROBE_SIZE_BYTES),
                "-analyzeduration",
                str(_ANALYZE_DURATION_MICROSECONDS),
                "-i",
                str(controlled_source_path),
                "-map",
                "0:a:0",
                "-t",
                str(_BOUNDED_DECODE_SECONDS),
                "-threads",
                "1",
                "-f",
                "null",
                "-",
            ],
            cwd=controlled_source_path.parent,
        )

    def decode_video(self, source_path: Path, *, has_audio: bool) -> None:
        """Decode a few primary video frames and matching bounded audio if present."""
        controlled_source_path = source_path.absolute()
        mappings = ["-map", "0:v:0"]
        if has_audio:
            mappings.extend(("-map", "0:a:0"))
        self._run_decode(
            [
                self._ffmpeg_executable,
                "-v",
                "error",
                "-nostdin",
                "-xerror",
                "-err_detect",
                "explode",
                "-probesize",
                str(_PROBE_SIZE_BYTES),
                "-analyzeduration",
                str(_ANALYZE_DURATION_MICROSECONDS),
                "-i",
                str(controlled_source_path),
                *mappings,
                "-t",
                str(_BOUNDED_DECODE_SECONDS),
                "-frames:v",
                str(_BOUNDED_VIDEO_FRAMES),
                "-threads",
                "1",
                "-f",
                "null",
                "-",
            ],
            cwd=controlled_source_path.parent,
        )

    def _run_probe(self, arguments: list[str], *, cwd: Path) -> bytes:
        process = self._start(arguments, stdout=subprocess.PIPE, cwd=cwd)
        stdout_pipe = process.stdout
        assert stdout_pipe is not None
        output = bytearray()
        output_exceeded = threading.Event()
        output_read_failed = threading.Event()

        def read_output() -> None:
            try:
                while len(output) <= _MAX_PROBE_OUTPUT_BYTES:
                    chunk = stdout_pipe.read(
                        min(4096, _MAX_PROBE_OUTPUT_BYTES + 1 - len(output))
                    )
                    if not chunk:
                        break
                    output.extend(chunk)
                if len(output) > _MAX_PROBE_OUTPUT_BYTES:
                    output_exceeded.set()
                    process.kill()
            except OSError:
                output_read_failed.set()
                with suppress(OSError):
                    process.kill()

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        return_code: int | None = None
        timed_out = False
        wait_failed = False
        try:
            return_code = process.wait(timeout=self._timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            with suppress(OSError):
                process.kill()
            try:
                process.wait()
            except OSError:
                wait_failed = True
        except OSError:
            wait_failed = True
            with suppress(OSError):
                process.kill()
            with suppress(OSError):
                process.wait()
        reader.join()
        try:
            stdout_pipe.close()
        except OSError:
            if output_read_failed.is_set():
                raise MediaToolSystemError("ffprobe_stdout_read") from None
            raise MediaToolSystemError("ffprobe_stdout_close") from None
        if output_read_failed.is_set():
            raise MediaToolSystemError("ffprobe_stdout_read") from None
        if wait_failed:
            raise MediaToolSystemError("process_wait") from None
        if timed_out:
            raise MediaRejectedError("ffprobe_timeout") from None
        if output_exceeded.is_set():
            raise MediaRejectedError("ffprobe_output_limit")
        assert return_code is not None
        if return_code != 0:
            raise MediaRejectedError("ffprobe")
        return bytes(output)

    def _run_decode(self, arguments: list[str], *, cwd: Path) -> None:
        process = self._start(arguments, stdout=subprocess.DEVNULL, cwd=cwd)
        try:
            return_code = process.wait(timeout=self._timeout_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise MediaRejectedError("ffmpeg_timeout") from None
        if return_code != 0:
            raise MediaRejectedError("ffmpeg_decode")

    @staticmethod
    def _start(arguments: list[str], *, stdout: int, cwd: Path) -> subprocess.Popen[bytes]:
        try:
            return subprocess.Popen(
                arguments,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=subprocess.DEVNULL,
                cwd=cwd,
            )
        except OSError:
            raise MediaToolSystemError("process_start") from None


def audio_parameters(probe: ProbeResult) -> AudioProbe:
    """Extract the required primary-audio values or reject an incomplete probe."""
    if not probe.audio_streams:
        raise MediaRejectedError("audio_stream")
    stream = probe.audio_streams[0]
    duration = _duration(stream, probe.format_duration_seconds)
    sample_rate = _positive_int(stream.get("sample_rate"))
    channels = _positive_int(stream.get("channels"))
    codec = _nonempty_string(stream.get("codec_name"))
    if duration is None or sample_rate is None or channels is None or codec is None:
        raise MediaRejectedError("audio_parameters")
    return AudioProbe(
        duration_seconds=duration,
        sample_rate_hz=sample_rate,
        channels=channels,
        codec=codec,
        bitrate_bps=_bitrate(stream.get("bit_rate"), probe.format_bitrate_bps),
    )


def video_parameters(probe: ProbeResult) -> VideoProbe:
    """Extract required primary-video values while ignoring attached cover pictures."""
    if not probe.video_streams:
        raise MediaRejectedError("video_stream")
    stream = probe.video_streams[0]
    duration = _duration(stream, probe.format_duration_seconds)
    codec = _nonempty_string(stream.get("codec_name"))
    width = _positive_int(stream.get("width"))
    height = _positive_int(stream.get("height"))
    fps = _frame_rate(stream.get("avg_frame_rate")) or _frame_rate(
        stream.get("r_frame_rate")
    )
    if duration is None or codec is None or width is None or height is None or fps is None:
        raise MediaRejectedError("video_parameters")
    audio_codec = None
    if probe.audio_streams:
        audio_codec = _nonempty_string(probe.audio_streams[0].get("codec_name"))
        if audio_codec is None:
            raise MediaRejectedError("audio_parameters")
    return VideoProbe(
        duration_seconds=duration,
        video_codec=codec,
        audio_codec=audio_codec,
        width=width,
        height=height,
        fps=fps,
        bitrate_bps=_bitrate(stream.get("bit_rate"), probe.format_bitrate_bps),
        has_audio=bool(probe.audio_streams),
    )


def _parse_probe_payload(payload: object) -> ProbeResult:
    if not isinstance(payload, dict):
        raise MediaToolSystemError("ffprobe_output")
    raw_format = payload.get("format")
    raw_streams = payload.get("streams")
    if not isinstance(raw_format, dict) or not isinstance(raw_streams, list):
        raise MediaToolSystemError("ffprobe_output")
    format_name = raw_format.get("format_name")
    if not isinstance(format_name, str) or not format_name:
        raise MediaToolSystemError("ffprobe_output")
    audio: list[dict[str, Any]] = []
    video: list[dict[str, Any]] = []
    for item in raw_streams:
        if not isinstance(item, dict):
            raise MediaToolSystemError("ffprobe_output")
        codec_type = item.get("codec_type")
        if codec_type == "audio":
            audio.append(item)
        elif codec_type == "video" and not _is_attached_picture(item):
            video.append(item)
    return ProbeResult(
        format_names=frozenset(format_name.split(",")),
        format_duration_seconds=_positive_float(raw_format.get("duration")),
        format_bitrate_bps=_positive_int(raw_format.get("bit_rate")),
        audio_streams=tuple(audio),
        video_streams=tuple(video),
    )


def _is_attached_picture(stream: dict[str, Any]) -> bool:
    disposition = stream.get("disposition")
    return isinstance(disposition, dict) and disposition.get("attached_pic") == 1


def _duration(stream: dict[str, Any], format_duration: float | None) -> float | None:
    return _positive_float(stream.get("duration")) or format_duration


def _bitrate(stream_value: object, format_value: int | None) -> int | None:
    return _positive_int(stream_value) or format_value


def _positive_int(value: object) -> int | None:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if parsed > 0 else None


def _positive_float(value: object) -> float | None:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if parsed > 0 and math.isfinite(parsed) else None


def _nonempty_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _frame_rate(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return None
    return parsed if parsed > 0 and math.isfinite(parsed) else None
