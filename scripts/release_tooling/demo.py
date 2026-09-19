"""Installed demo generation, media properties and confinement checks."""

from __future__ import annotations

import json
import shutil
import wave
from pathlib import Path
from typing import Any

from PIL import Image

from . import common

_DEMO_NAMES = {
    ".png": "fakedetector-demo-copy-move.png",
    ".wav": "fakedetector-demo-audio.wav",
    ".mp4": "fakedetector-demo-video.mp4",
}


def _probe_demo_media(media: dict[str, Path], *, env: dict[str, str]) -> dict[str, Any]:
    image_path = media[".png"]
    with Image.open(image_path) as image:
        image.load()
        repeated_region = (
            image.crop((48, 64, 160, 176)).tobytes() == image.crop((320, 300, 432, 412)).tobytes()
        )
        image_evidence = {
            "filename": image_path.name,
            "format": image.format,
            "mode": image.mode,
            "width": image.width,
            "height": image.height,
            "repeated_region": repeated_region,
            "sha256": common._sha256_file(image_path),
        }
    if not (
        image_evidence["format"] == "PNG"
        and image_evidence["mode"] == "RGB"
        and (image_evidence["width"], image_evidence["height"]) == (512, 512)
        and repeated_region
    ):
        raise common.ReleaseVerificationError("demo", "Generated PNG properties are invalid.")

    audio_path = media[".wav"]
    with wave.open(str(audio_path), "rb") as audio:
        audio_evidence = {
            "filename": audio_path.name,
            "channels": audio.getnchannels(),
            "sample_width_bytes": audio.getsampwidth(),
            "sample_rate_hz": audio.getframerate(),
            "frame_count": audio.getnframes(),
            "compression": audio.getcomptype(),
            "sha256": common._sha256_file(audio_path),
        }
    if (
        audio_evidence["channels"],
        audio_evidence["sample_width_bytes"],
        audio_evidence["sample_rate_hz"],
        audio_evidence["frame_count"],
        audio_evidence["compression"],
    ) != (1, 2, 8000, 8000, "NONE"):
        raise common.ReleaseVerificationError("demo", "Generated WAV properties are invalid.")

    ffprobe = shutil.which("ffprobe", path=env.get("PATH"))
    if ffprobe is None:
        raise common.ReleaseVerificationError("demo", "ffprobe disappeared from PATH.")
    video_path = media[".mp4"]
    completed = common._run_command(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_type,width,height,r_frame_rate:format=duration",
            "-of",
            "json",
            str(video_path),
        ],
        cwd=video_path.parent,
        env=env,
        timeout=15.0,
        phase="demo",
    )
    try:
        video_payload = json.loads(completed.stdout)
        stream = video_payload["streams"][0]
        duration = float(video_payload["format"]["duration"])
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        raise common.ReleaseVerificationError("demo", "Generated MP4 probe is invalid.") from None
    video_evidence = {
        "filename": video_path.name,
        "codec_type": stream.get("codec_type"),
        "width": stream.get("width"),
        "height": stream.get("height"),
        "frame_rate": stream.get("r_frame_rate"),
        "duration_seconds": duration,
        "sha256": common._sha256_file(video_path),
    }
    if not (
        video_evidence["codec_type"] == "video"
        and (video_evidence["width"], video_evidence["height"]) == (64, 64)
        and video_evidence["frame_rate"] == "2/1"
        and 3.0 <= duration <= 4.0
    ):
        raise common.ReleaseVerificationError("demo", "Generated MP4 properties are invalid.")
    return {"image": image_evidence, "audio": audio_evidence, "video": video_evidence}


def _generate_demo_media(
    *,
    python: Path,
    extraction: Path,
    work: Path,
    env: dict[str, str],
) -> tuple[dict[str, Path], dict[str, Any]]:
    output = work / "demo-media"
    generator = extraction / "generate_release_demo_media.py"
    command = [str(python), str(generator), "--output-dir", str(output)]
    common._run_command(
        command,
        cwd=work,
        env=env,
        timeout=common._PHASE_TIMEOUTS["demo"],
        phase="demo",
    )
    media = {suffix: output / name for suffix, name in _DEMO_NAMES.items()}
    if not all(path.is_file() for path in media.values()):
        raise common.ReleaseVerificationError(
            "demo", "Release-kit generator did not create all demo files."
        )
    evidence = _probe_demo_media(media, env=env)
    evidence["generation"] = {
        "status": "passed",
        "generator_source": "verified ZIP extraction",
        "python": "fresh installed environment",
    }
    return media, evidence


def _verify_no_demo_copies_outside_demo(work: Path) -> bool:
    demo_root = (work / "demo-media").resolve()
    for path in work.rglob("*"):
        if path.is_file() and path.name in _DEMO_NAMES.values():
            resolved = path.resolve()
            if demo_root not in resolved.parents:
                return False
    return True
