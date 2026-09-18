"""Generate the deterministic FakeDetector Stage 10 demo media set."""

from __future__ import annotations

import argparse
import json
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from contextlib import suppress
from pathlib import Path

import numpy as np
from PIL import Image

_IMAGE_NAME = "fakedetector-demo-copy-move.png"
_AUDIO_NAME = "fakedetector-demo-audio.wav"
_VIDEO_NAME = "fakedetector-demo-video.mp4"
_OUTPUT_NAMES = (_IMAGE_NAME, _AUDIO_NAME, _VIDEO_NAME)


class DemoGenerationError(RuntimeError):
    """Safe user-facing failure while generating demo media."""


def _require_executable(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise DemoGenerationError(f"Required executable is not available on PATH: {name}")
    try:
        completed = subprocess.run(
            [executable, "-version"],
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5.0,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        raise DemoGenerationError(f"Required executable could not be started: {name}") from None
    if completed.returncode != 0:
        raise DemoGenerationError(f"Required executable failed its version check: {name}")
    return executable


def _generate_image(path: Path) -> None:
    rng = np.random.default_rng(217)
    canvas = np.full((512, 512, 3), 24, dtype=np.uint8)
    patch = rng.integers(0, 256, size=(112, 112, 3), dtype=np.uint8)
    canvas[64:176, 48:160] = patch
    canvas[300:412, 320:432] = patch
    with Image.fromarray(canvas) as image:
        image.save(path, format="PNG")


def _generate_audio(path: Path) -> None:
    samples = [1_000] * 8_000
    samples[::100] = [32_767] * len(samples[::100])
    payload = struct.pack(f"<{len(samples)}h", *samples)
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8_000)
        audio.writeframes(payload)


def _generate_video(path: Path, *, ffmpeg: str) -> None:
    try:
        completed = subprocess.run(
            [
                ffmpeg,
                "-v",
                "error",
                "-n",
                "-nostdin",
                "-f",
                "lavfi",
                "-i",
                "color=c=blue:s=64x64:r=2",
                "-t",
                "3.2",
                "-c:v",
                "mpeg4",
                "-pix_fmt",
                "yuv420p",
                str(path),
            ],
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=15.0,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        raise DemoGenerationError("FFmpeg could not generate the demo video.") from None
    if completed.returncode != 0:
        raise DemoGenerationError(
            "FFmpeg lacks a capability required for the demo video recipe."
        )


def _validate_image(path: Path) -> None:
    try:
        with Image.open(path) as image:
            image.load()
            if image.format != "PNG" or image.mode != "RGB" or image.size != (512, 512):
                raise DemoGenerationError("Generated image failed validation.")
            if image.crop((48, 64, 160, 176)).tobytes() != image.crop(
                (320, 300, 432, 412)
            ).tobytes():
                raise DemoGenerationError("Generated image lacks its repeated region.")
    except (OSError, ValueError):
        raise DemoGenerationError("Generated image failed validation.") from None


def _validate_audio(path: Path) -> None:
    try:
        with wave.open(str(path), "rb") as audio:
            properties = (
                audio.getnchannels(),
                audio.getsampwidth(),
                audio.getframerate(),
                audio.getnframes(),
                audio.getcomptype(),
            )
    except (OSError, EOFError, wave.Error):
        raise DemoGenerationError("Generated audio failed validation.") from None
    if properties != (1, 2, 8_000, 8_000, "NONE"):
        raise DemoGenerationError("Generated audio failed validation.")


def _validate_video(path: Path, *, ffprobe: str) -> None:
    try:
        completed = subprocess.run(
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
                str(path),
            ],
            shell=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=10.0,
            check=False,
        )
        payload = json.loads(completed.stdout)
        stream = payload["streams"][0]
        duration = float(payload["format"]["duration"])
    except (
        OSError,
        subprocess.SubprocessError,
        ValueError,
        KeyError,
        IndexError,
        json.JSONDecodeError,
    ):
        raise DemoGenerationError("Generated video failed FFprobe validation.") from None
    if (
        completed.returncode != 0
        or stream.get("codec_type") != "video"
        or stream.get("width") != 64
        or stream.get("height") != 64
        or stream.get("r_frame_rate") != "2/1"
        or not 3.0 <= duration <= 4.0
    ):
        raise DemoGenerationError("Generated video failed FFprobe validation.")


def _copy_outputs(staging: Path, output: Path) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise DemoGenerationError("Output directory must be empty.")

    created: list[Path] = []
    try:
        for name in _OUTPUT_NAMES:
            target = output / name
            destination = target.open("xb")
            created.append(target.resolve())
            with (staging / name).open("rb") as source, destination:
                shutil.copyfileobj(source, destination)
    except OSError:
        for target in created:
            with suppress(OSError):
                target.unlink()
        raise DemoGenerationError(
            "Generated media could not be copied to the output directory."
        ) from None
    return created


def generate_demo_media(output_directory: Path) -> list[Path]:
    """Generate, validate, and publish the three deterministic demo files."""
    output = output_directory.expanduser().resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise DemoGenerationError("Output directory must be absent or empty.")
    output.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = _require_executable("ffmpeg")
    ffprobe = _require_executable("ffprobe")
    with tempfile.TemporaryDirectory(prefix="fakedetector-demo-", dir=output.parent) as temp:
        staging = Path(temp)
        image_path = staging / _IMAGE_NAME
        audio_path = staging / _AUDIO_NAME
        video_path = staging / _VIDEO_NAME
        _generate_image(image_path)
        _generate_audio(audio_path)
        _generate_video(video_path, ffmpeg=ffmpeg)
        _validate_image(image_path)
        _validate_audio(audio_path)
        _validate_video(video_path, ffprobe=ffprobe)
        return _copy_outputs(staging, output)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate deterministic image, audio, and video for the FakeDetector demo."
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        generated = generate_demo_media(args.output_dir)
    except DemoGenerationError as error:
        print(f"Demo media generation failed: {error}", file=sys.stderr)
        return 1
    except OSError:
        print("Demo media generation failed: output directory is unavailable.", file=sys.stderr)
        return 1
    for path in generated:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
