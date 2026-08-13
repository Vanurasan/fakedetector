"""Unit tests for the narrow bounded FFmpeg subprocess boundary."""

from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import pytest

import fakedetector.intake.media_tools as media_tools_module
from fakedetector.intake.media_tools import (
    FFmpegMediaInspector,
    MediaRejectedError,
    MediaToolSystemError,
    _parse_probe_payload,
    audio_parameters,
    video_parameters,
)


def probe_payload(*, audio: bool = True, video: bool = False) -> dict[str, object]:
    streams: list[dict[str, object]] = []
    if audio:
        streams.append(
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "48000",
                "channels": 2,
                "duration": "1.5",
            }
        )
    if video:
        streams.append(
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "avg_frame_rate": "30000/1001",
                "duration": "1.5",
            }
        )
    return {
        "format": {"format_name": "mov,mp4,m4a", "duration": "1.5"},
        "streams": streams,
    }


class FakeProcess:
    def __init__(self, *, output: bytes = b"", return_code: int = 0) -> None:
        self.stdout = io.BytesIO(output)
        self.return_code = return_code
        self.killed = False
        self.wait_calls = 0

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        return self.return_code

    def kill(self) -> None:
        self.killed = True


class TimeoutProcess(FakeProcess):
    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        if self.wait_calls == 1:
            raise subprocess.TimeoutExpired("safe-executable", timeout)
        return self.return_code


def test_probe_uses_bounded_safe_arguments_and_parses_only_required_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "controlled-source"
    calls: list[tuple[list[str], dict[str, object]]] = []
    process = FakeProcess(output=json.dumps(probe_payload()).encode())

    def fake_popen(arguments: list[str], **kwargs: object) -> FakeProcess:
        calls.append((arguments, kwargs))
        return process

    monkeypatch.setattr(media_tools_module.subprocess, "Popen", fake_popen)

    probe = FFmpegMediaInspector(ffprobe_executable="trusted-ffprobe").probe(source_path)

    assert audio_parameters(probe).sample_rate_hz == 48_000
    arguments, kwargs = calls[0]
    assert arguments[0] == "trusted-ffprobe"
    assert arguments[-1] == str(source_path)
    assert "-show_entries" in arguments
    assert "tags" not in " ".join(arguments)
    assert kwargs == {
        "shell": False,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.DEVNULL,
    }


@pytest.mark.parametrize(("media_type", "has_audio"), [("audio", False), ("video", True)])
def test_bounded_decode_uses_null_sink_without_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    media_type: str,
    has_audio: bool,
) -> None:
    source_path = tmp_path / "source"
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_popen(arguments: list[str], **kwargs: object) -> FakeProcess:
        calls.append((arguments, kwargs))
        return FakeProcess()

    monkeypatch.setattr(media_tools_module.subprocess, "Popen", fake_popen)
    inspector = FFmpegMediaInspector(ffmpeg_executable="trusted-ffmpeg")

    if media_type == "audio":
        inspector.decode_audio(source_path)
    else:
        inspector.decode_video(source_path, has_audio=has_audio)

    arguments, kwargs = calls[0]
    assert arguments[0] == "trusted-ffmpeg"
    assert "-nostdin" in arguments
    assert arguments[arguments.index("-t") + 1] == "1"
    assert arguments[-3:] == ["-f", "null", "-"]
    assert str(source_path) in arguments
    assert kwargs["shell"] is False
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["stdout"] == subprocess.DEVNULL
    assert kwargs["stderr"] == subprocess.DEVNULL
    if media_type == "video":
        assert arguments[arguments.index("-frames:v") + 1] == "3"
        assert "0:v:0" in arguments
        assert "0:a:0" in arguments


def test_process_start_failure_is_safe_system_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = "PRIVATE EXECUTABLE PATH"

    def fail_popen(arguments: list[str], **kwargs: object) -> FakeProcess:
        raise OSError(sentinel)

    monkeypatch.setattr(media_tools_module.subprocess, "Popen", fail_popen)

    with pytest.raises(MediaToolSystemError) as error_info:
        FFmpegMediaInspector().probe(tmp_path / "source")

    assert error_info.value.phase == "process_start"
    assert sentinel not in str(error_info.value)
    assert error_info.value.__cause__ is None


@pytest.mark.parametrize("output", [b"not-json", b"[]", b'{"format": {}, "streams": []}'])
def test_successful_malformed_probe_output_is_system_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: bytes,
) -> None:
    monkeypatch.setattr(
        media_tools_module.subprocess,
        "Popen",
        lambda arguments, **kwargs: FakeProcess(output=output),
    )

    with pytest.raises(MediaToolSystemError, match="infrastructure") as error_info:
        FFmpegMediaInspector().probe(tmp_path / "source")

    assert error_info.value.phase == "ffprobe_output"


def test_probe_output_limit_kills_process_and_rejects_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = FakeProcess(output=b"x" * (64 * 1024 + 1))
    monkeypatch.setattr(
        media_tools_module.subprocess,
        "Popen",
        lambda arguments, **kwargs: process,
    )

    with pytest.raises(MediaRejectedError) as error_info:
        FFmpegMediaInspector().probe(tmp_path / "source")

    assert error_info.value.phase == "ffprobe_output_limit"
    assert process.killed


@pytest.mark.parametrize("operation", ["probe", "decode"])
def test_timeout_kills_and_reaps_process_as_normative_media_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    output = json.dumps(probe_payload()).encode() if operation == "probe" else b""
    process = TimeoutProcess(output=output)
    monkeypatch.setattr(
        media_tools_module.subprocess,
        "Popen",
        lambda arguments, **kwargs: process,
    )
    inspector = FFmpegMediaInspector(timeout_seconds=0.01)

    with pytest.raises(MediaRejectedError) as error_info:
        if operation == "probe":
            inspector.probe(tmp_path / "source")
        else:
            inspector.decode_audio(tmp_path / "source")

    assert error_info.value.phase.endswith("timeout")
    assert process.killed
    assert process.wait_calls == 2


@pytest.mark.parametrize("operation", ["probe", "decode"])
def test_decoder_nonzero_return_is_normative_rejection_without_raw_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    process = FakeProcess(return_code=7)
    monkeypatch.setattr(
        media_tools_module.subprocess,
        "Popen",
        lambda arguments, **kwargs: process,
    )
    inspector = FFmpegMediaInspector()

    with pytest.raises(MediaRejectedError) as error_info:
        if operation == "probe":
            inspector.probe(tmp_path / "source")
        else:
            inspector.decode_audio(tmp_path / "source")

    assert "PRIVATE" not in str(error_info.value)


def test_attached_picture_does_not_make_audio_container_video() -> None:
    payload = probe_payload(audio=True)
    streams = payload["streams"]
    assert isinstance(streams, list)
    streams.append(
        {
            "codec_type": "video",
            "codec_name": "mjpeg",
            "width": 100,
            "height": 100,
            "avg_frame_rate": "0/0",
            "disposition": {"attached_pic": 1},
        }
    )

    probe = _parse_probe_payload(payload)

    assert len(probe.audio_streams) == 1
    assert probe.video_streams == ()


def test_optional_bitrate_and_audio_codec_remain_none_when_absent() -> None:
    audio = audio_parameters(_parse_probe_payload(probe_payload(audio=True)))
    video = video_parameters(_parse_probe_payload(probe_payload(audio=False, video=True)))

    assert audio.bitrate_bps is None
    assert video.bitrate_bps is None
    assert video.has_audio is False
    assert video.audio_codec is None
