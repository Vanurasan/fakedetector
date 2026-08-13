"""Small deterministic legal media fixtures generated without network access."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture(scope="session")
def media_files(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Generate the complete canonical MVP matrix in pytest-owned storage."""
    root = tmp_path_factory.mktemp("canonical-media")
    image = Image.new("RGB", (16, 12), color=(12, 34, 56))
    image.save(root / "sample.jpg", format="JPEG")
    shutil.copyfile(root / "sample.jpg", root / "sample.jpeg")
    image.save(root / "sample.png", format="PNG")
    image.save(root / "sample.webp", format="WEBP", lossless=True)
    second_frame = Image.new("RGB", (16, 12), color=(65, 43, 21))
    image.save(
        root / "animated.png",
        format="PNG",
        save_all=True,
        append_images=[second_frame],
        duration=50,
        loop=0,
    )
    image.save(
        root / "animated.webp",
        format="WEBP",
        save_all=True,
        append_images=[second_frame],
        duration=50,
        loop=0,
        lossless=True,
    )

    ffmpeg = shutil.which("ffmpeg")
    assert ffmpeg is not None, "FFmpeg is required to generate canonical test media"
    audio_outputs = {
        "wav": [],
        "mp3": ["-c:a", "libmp3lame"],
        "flac": ["-c:a", "flac"],
        "m4a": ["-c:a", "aac"],
    }
    for extension, codec_arguments in audio_outputs.items():
        _run_ffmpeg(
            ffmpeg,
            [
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:sample_rate=8000",
                "-t",
                "0.25",
                *codec_arguments,
                str(root / f"sample.{extension}"),
            ],
        )

    for extension in ("mp4", "mov", "avi", "mkv"):
        _run_ffmpeg(
            ffmpeg,
            [
                "-f",
                "lavfi",
                "-i",
                "color=c=blue:s=32x24:r=10",
                "-t",
                "0.4",
                "-c:v",
                "mpeg4",
                "-pix_fmt",
                "yuv420p",
                str(root / f"sample.{extension}"),
            ],
        )
    _run_ffmpeg(
        ffmpeg,
        [
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=32x24:r=10",
            "-t",
            "0.4",
            "-c:v",
            "libvpx-vp9",
            str(root / "unsupported.webm"),
        ],
    )
    return {
        path.name.replace("sample.", "").replace("unsupported.", ""): path
        for path in root.iterdir()
    }


def _run_ffmpeg(executable: str, arguments: list[str]) -> None:
    subprocess.run(
        [executable, "-v", "error", "-y", "-nostdin", *arguments],
        shell=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=15.0,
        check=True,
    )
