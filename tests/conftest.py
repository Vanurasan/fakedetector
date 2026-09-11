"""Small deterministic legal media fixtures generated without network access."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable, Iterator
from io import BytesIO
from multiprocessing.process import BaseProcess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from fakedetector.analyzers._worker import _MultiprocessingSpawnBackend


@pytest.fixture(autouse=True)
def stage8_access_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide non-secret deterministic credentials for enabled test channels."""
    monkeypatch.setenv("MEDIA_ANALYZER_API_TOKEN", "stage8-test-token")
    monkeypatch.setenv(
        "MEDIA_ANALYZER_WEBUI_CREDENTIALS",
        "stage8-user:stage8-password",
    )


class _ProbeInterruption(BaseException):
    pass


@pytest.fixture(scope="session")
def copy_move_png_bytes() -> bytes:
    """Generate the deterministic Stage 6 copy-move correspondence image."""
    rng = np.random.default_rng(217)
    canvas = np.full((512, 512, 3), 24, dtype=np.uint8)
    patch = rng.integers(0, 256, size=(112, 112, 3), dtype=np.uint8)
    canvas[64:176, 48:160] = patch
    canvas[300:412, 320:432] = patch
    output = BytesIO()
    with Image.fromarray(canvas) as image:
        image.save(output, format="PNG")
    return output.getvalue()


@pytest.fixture(params=[KeyboardInterrupt, SystemExit, _ProbeInterruption])
def process_interruption(request: pytest.FixtureRequest) -> BaseException:
    return request.param("PRIVATE process interruption")


@pytest.fixture
def real_worker_processes(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[BaseProcess]]:
    """Track real spawn children and reap even when a test replaces stop/join methods."""
    processes: list[BaseProcess] = []
    teardowns: list[Callable[[], None]] = []
    create_process = _MultiprocessingSpawnBackend.create_process
    close_process = BaseProcess.close

    def checked_close(process) -> None:
        if process.pid is not None:
            assert not process.is_alive()
            process.join(timeout=0.0)
            assert process.exitcode is not None
        close_process(process)

    monkeypatch.setattr(BaseProcess, "close", checked_close)

    def track_process(self, **kwargs):
        process = create_process(self, **kwargs)
        processes.append(process)
        is_alive, join, kill = process.is_alive, process.join, process.kill

        def teardown() -> None:
            if process._closed:
                return
            if process.pid is not None:
                if is_alive():
                    kill()
                join(timeout=5.0)
                assert not is_alive()
                assert process.exitcode is not None
            close_process(process)

        teardowns.append(teardown)
        return process

    monkeypatch.setattr(_MultiprocessingSpawnBackend, "create_process", track_process)
    try:
        yield processes
    finally:
        for teardown in teardowns:
            teardown()


@pytest.fixture
def real_subprocesses(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[subprocess.Popen[bytes]]]:
    """Keep original stop/wait operations so injected failures cannot leak probe children."""
    processes: list[subprocess.Popen[bytes]] = []
    teardowns: list[Callable[[], None]] = []
    popen = subprocess.Popen

    def track_process(*args, **kwargs):
        process = popen(*args, **kwargs)
        processes.append(process)
        poll, wait, kill = process.poll, process.wait, process.kill
        stdout = process.stdout
        close_stdout = None if stdout is None else stdout.close

        def teardown() -> None:
            if poll() is None:
                kill()
            assert wait(timeout=5.0) == process.returncode
            assert poll() is not None
            if close_stdout is not None:
                close_stdout()

        teardowns.append(teardown)
        return process

    monkeypatch.setattr(subprocess, "Popen", track_process)
    try:
        yield processes
    finally:
        for teardown in teardowns:
            teardown()


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
        metadata_arguments = ["-metadata", "title=webm"] if extension == "mkv" else []
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
                *metadata_arguments,
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
