"""Unit tests for the narrow bounded FFmpeg subprocess boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import fakedetector.intake.media_tools as media_tools_module
from fakedetector.core._bounded_process import (
    ProcessInfrastructureError,
    ProcessInfrastructurePhase,
    ProcessOutputLimitError,
    ProcessResult,
    ProcessTimeoutError,
)
from fakedetector.intake.media_tools import (
    FFmpegMediaInspector,
    MediaRejectedError,
    MediaToolSystemError,
    _parse_probe_payload,
    audio_parameters,
    video_parameters,
)


class _UnconfirmedSafetyBarrier:
    def try_confirm_safe(self) -> bool:
        return False


def _process_infrastructure_error(
    phase: ProcessInfrastructurePhase,
) -> ProcessInfrastructureError:
    if phase == "termination":
        return ProcessInfrastructureError(
            phase,
            _cleanup_safety_barrier=_UnconfirmedSafetyBarrier(),
        )
    return ProcessInfrastructureError(phase)


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


def test_probe_uses_bounded_safe_arguments_and_parses_only_required_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_name = "PRIVATE-user-title.wav"
    workspace_path = tmp_path / "application-owned" / "system-analysis-id"
    workspace_path.mkdir(parents=True)
    source_path = workspace_path / "source"
    source_path.touch()
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(arguments: list[str], **kwargs: object) -> ProcessResult:
        calls.append((arguments, kwargs))
        return ProcessResult(return_code=0, stdout=json.dumps(probe_payload()).encode())

    monkeypatch.setattr(media_tools_module, "run_bounded_process", fake_run)

    probe = FFmpegMediaInspector(ffprobe_executable="trusted-ffprobe").probe(source_path)

    assert audio_parameters(probe).sample_rate_hz == 48_000
    arguments, kwargs = calls[0]
    assert arguments[0] == "trusted-ffprobe"
    assert arguments[-1] == str(source_path)
    assert "-show_entries" in arguments
    assert "tags" not in " ".join(arguments)
    assert kwargs == {
        "cwd": workspace_path,
        "timeout_seconds": 15.0,
        "stdout_limit_bytes": 64 * 1024,
    }
    assert original_name not in str(kwargs["cwd"])


@pytest.mark.parametrize(("media_type", "has_audio"), [("audio", False), ("video", True)])
def test_bounded_decode_uses_null_sink_without_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    media_type: str,
    has_audio: bool,
) -> None:
    original_name = "PRIVATE-user-title.mkv"
    workspace_path = tmp_path / "application-owned" / "system-analysis-id"
    workspace_path.mkdir(parents=True)
    source_path = workspace_path / "source"
    source_path.touch()
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(arguments: list[str], **kwargs: object) -> ProcessResult:
        calls.append((arguments, kwargs))
        return ProcessResult(return_code=0, stdout=None)

    monkeypatch.setattr(media_tools_module, "run_bounded_process", fake_run)
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
    assert kwargs["cwd"] == workspace_path
    assert kwargs["timeout_seconds"] == 15.0
    assert "stdout_limit_bytes" not in kwargs
    assert original_name not in str(kwargs["cwd"])
    if media_type == "video":
        assert arguments[arguments.index("-frames:v") + 1] == "3"
        assert "0:v:0" in arguments
        assert "0:a:0" in arguments


def test_process_start_failure_is_safe_system_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_run(arguments: list[str], **kwargs: object) -> ProcessResult:
        raise ProcessInfrastructureError("start")

    monkeypatch.setattr(media_tools_module, "run_bounded_process", fail_run)

    with pytest.raises(MediaToolSystemError) as error_info:
        FFmpegMediaInspector().probe(tmp_path / "source")

    assert error_info.value.phase == "process_start"
    assert error_info.value.__cause__ is None


@pytest.mark.parametrize("output", [b"not-json", b"[]", b'{"format": {}, "streams": []}'])
def test_successful_malformed_probe_output_is_system_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: bytes,
) -> None:
    monkeypatch.setattr(
        media_tools_module,
        "run_bounded_process",
        lambda arguments, **kwargs: ProcessResult(return_code=0, stdout=output),
    )

    with pytest.raises(MediaToolSystemError, match="infrastructure") as error_info:
        FFmpegMediaInspector().probe(tmp_path / "source")

    assert error_info.value.phase == "ffprobe_output"


def test_probe_output_limit_maps_to_normative_rejection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_run(arguments: list[str], **kwargs: object) -> ProcessResult:
        raise ProcessOutputLimitError

    monkeypatch.setattr(
        media_tools_module,
        "run_bounded_process",
        fail_run,
    )

    with pytest.raises(MediaRejectedError) as error_info:
        FFmpegMediaInspector().probe(tmp_path / "source")

    assert error_info.value.phase == "ffprobe_output_limit"


@pytest.mark.parametrize(
    ("process_phase", "media_phase"),
    [
        ("stdout_read", "ffprobe_stdout_read"),
        ("stdout_close", "ffprobe_stdout_close"),
        ("wait", "process_wait"),
        ("termination", "process_wait"),
    ],
)
def test_probe_infrastructure_failure_preserves_safe_phase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    process_phase: ProcessInfrastructurePhase,
    media_phase: str,
) -> None:
    def fail_run(arguments: list[str], **kwargs: object) -> ProcessResult:
        raise _process_infrastructure_error(process_phase)

    monkeypatch.setattr(
        media_tools_module,
        "run_bounded_process",
        fail_run,
    )

    with pytest.raises(MediaToolSystemError) as error_info:
        FFmpegMediaInspector().probe(tmp_path / "source")

    assert error_info.value.phase == media_phase
    assert error_info.value.__cause__ is None


@pytest.mark.parametrize("operation", ["probe", "decode"])
def test_timeout_maps_to_normative_media_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    def fail_run(arguments: list[str], **kwargs: object) -> ProcessResult:
        raise ProcessTimeoutError

    monkeypatch.setattr(
        media_tools_module,
        "run_bounded_process",
        fail_run,
    )
    inspector = FFmpegMediaInspector(timeout_seconds=0.01)

    with pytest.raises(MediaRejectedError) as error_info:
        if operation == "probe":
            inspector.probe(tmp_path / "source")
        else:
            inspector.decode_audio(tmp_path / "source")

    assert error_info.value.phase.endswith("timeout")


@pytest.mark.parametrize("operation", ["probe", "decode"])
def test_decoder_nonzero_return_is_normative_rejection_without_raw_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    monkeypatch.setattr(
        media_tools_module,
        "run_bounded_process",
        lambda arguments, **kwargs: ProcessResult(
            return_code=7,
            stdout=json.dumps(probe_payload()).encode() if operation == "probe" else None,
        ),
    )
    inspector = FFmpegMediaInspector()

    with pytest.raises(MediaRejectedError) as error_info:
        if operation == "probe":
            inspector.probe(tmp_path / "source")
        else:
            inspector.decode_audio(tmp_path / "source")

    assert "PRIVATE" not in str(error_info.value)


def test_decode_infrastructure_failure_maps_to_safe_system_phase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_run(arguments: list[str], **kwargs: object) -> ProcessResult:
        raise _process_infrastructure_error("termination")

    monkeypatch.setattr(media_tools_module, "run_bounded_process", fail_run)

    with pytest.raises(MediaToolSystemError) as error_info:
        FFmpegMediaInspector().decode_audio(tmp_path / "source")

    assert error_info.value.phase == "process_wait"
    assert error_info.value.__cause__ is None


def test_source_path_with_metacharacters_remains_one_argv_element(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "trusted space & semicolon; dollar$(literal)" / "source"
    observed_arguments: list[str] = []

    def fake_run(arguments: list[str], **kwargs: object) -> ProcessResult:
        observed_arguments.extend(arguments)
        return ProcessResult(return_code=0, stdout=json.dumps(probe_payload()).encode())

    monkeypatch.setattr(media_tools_module, "run_bounded_process", fake_run)

    FFmpegMediaInspector().probe(source_path)

    assert observed_arguments[-1] == str(source_path.absolute())
    assert observed_arguments.count(str(source_path.absolute())) == 1


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
