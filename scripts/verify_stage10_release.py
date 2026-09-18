"""Assemble and exercise the Stage 10 MVP release handoff."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import tomllib
import wave
import zipfile
from collections import deque
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

import verify_stage10_package as package_verifier
import yaml
from PIL import Image

_TOOL_VERSION = "1.0.0"
_MANIFEST_NAME = "release-manifest.json"
_REPORT_NAME = "verification-report.json"
_EXPECTED_ANALYZERS = {
    ".png": (
        ("image_metadata_consistency", "1.0.0"),
        ("image_copy_move_correspondence", "1.0.0"),
    ),
    ".wav": (("audio_pcm_quality", "1.0.0"),),
    ".mp4": (("video_sampled_frame_quality", "1.0.0"),),
}
_MEDIA_MIME = {
    ".png": "image/png",
    ".wav": "audio/wav",
    ".mp4": "video/mp4",
}
_DEMO_NAMES = {
    ".png": "fakedetector-demo-copy-move.png",
    ".wav": "fakedetector-demo-audio.wav",
    ".mp4": "fakedetector-demo-video.mp4",
}
_COMPANION_SOURCES = {
    "config.example.yaml": Path("config/config.example.yaml"),
    ".env.example": Path(".env.example"),
    "generate_stage10_demo_media.py": Path("scripts/generate_stage10_demo_media.py"),
    "MVP_HANDOFF.md": Path("docs/MVP_HANDOFF.md"),
    "CHANGELOG.md": Path("docs/CHANGELOG.md"),
}
_PHASE_TIMEOUTS = {
    "build": 300.0,
    "constraints": 120.0,
    "venv": 120.0,
    "install": 300.0,
    "probe": 60.0,
    "demo": 60.0,
    "startup": 30.0,
    "analysis": 120.0,
    "shutdown": 30.0,
}
_MAX_HTTP_BODY_BYTES = 2 * 1024 * 1024
_SERVER_TAIL_LINES = 200


class ReleaseGateError(RuntimeError):
    """Safe release-gate failure with a stable phase."""

    def __init__(
        self,
        phase: str,
        message: str,
        *,
        analysis_id: str | None = None,
        process_returncode: int | None = None,
        server_output_tail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.phase = phase
        self.analysis_id = analysis_id
        self.process_returncode = process_returncode
        self.server_output_tail = server_output_tail


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Request | None:
        del req, fp, code, msg, headers, newurl
        return None


class _ServerProcess:
    def __init__(self, process: subprocess.Popen[str], port: int) -> None:
        self.process = process
        self.port = port
        self.stdout_lines: deque[str] = deque(maxlen=_SERVER_TAIL_LINES)
        self.stderr_lines: deque[str] = deque(maxlen=_SERVER_TAIL_LINES)
        assert process.stdout is not None
        assert process.stderr is not None
        self._threads = (
            threading.Thread(
                target=self._drain,
                args=(process.stdout, self.stdout_lines),
                daemon=True,
            ),
            threading.Thread(
                target=self._drain,
                args=(process.stderr, self.stderr_lines),
                daemon=True,
            ),
        )
        for thread in self._threads:
            thread.start()

    @staticmethod
    def _drain(stream: Any, destination: deque[str]) -> None:
        try:
            for line in stream:
                destination.append(line.rstrip())
        finally:
            stream.close()

    def join_readers(self) -> None:
        for thread in self._threads:
            thread.join(timeout=2.0)

    def output_tail(self, secret_values: tuple[str, ...]) -> str:
        lines = [*(f"stdout: {line}" for line in self.stdout_lines)]
        lines.extend(f"stderr: {line}" for line in self.stderr_lines)
        return _redact("\n".join(lines[-_SERVER_TAIL_LINES:]), secret_values)


def _announce(phase: str) -> None:
    print(f"[stage10-release] {phase}", file=sys.stderr, flush=True)


def _redact(value: str, secret_values: tuple[str, ...]) -> str:
    redacted = value
    for secret_value in sorted(secret_values, key=len, reverse=True):
        if secret_value:
            redacted = redacted.replace(secret_value, "<redacted>")
    return redacted


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _certification_state(*, development: bool, source_status: list[str]) -> dict[str, Any]:
    source_tree_clean = not source_status
    if not development and not source_tree_clean:
        raise ReleaseGateError(
            "source",
            "Strict certification requires a clean tracked and untracked source tree.",
        )
    return {
        "certification_mode": "development" if development else "strict",
        "source_tree_clean": source_tree_clean,
        "certified": bool(not development and source_tree_clean),
    }


def _project_identity(pyproject: dict[str, Any]) -> tuple[str, str]:
    project = pyproject.get("project")
    if not isinstance(project, dict):
        raise ReleaseGateError("source", "pyproject.toml lacks [project] metadata.")
    name = project.get("name")
    version = project.get("version")
    if not isinstance(name, str) or not name or not isinstance(version, str) or not version:
        raise ReleaseGateError("source", "pyproject.toml project name/version is invalid.")
    return name, version


def _require_stable_source_sha(*, initial_sha: str, final_sha: str) -> None:
    if final_sha != initial_sha:
        raise ReleaseGateError("source", "HEAD changed during the release gate.")


def _expected_kit_names(wheel_filename: str) -> set[str]:
    return {
        wheel_filename,
        "runtime-constraints.txt",
        *_COMPANION_SOURCES,
        _MANIFEST_NAME,
    }


def _validate_kit_inventory(actual_names: set[str], expected_names: set[str]) -> None:
    missing = sorted(expected_names - actual_names)
    unexpected = sorted(actual_names - expected_names)
    if missing or unexpected:
        raise ReleaseGateError(
            "release_kit",
            "Release kit inventory differs from the required inventory: "
            + json.dumps({"missing": missing, "unexpected": unexpected}, sort_keys=True),
        )


def _validate_zip_member_names(names: list[str], expected_names: set[str]) -> None:
    if len(names) != len(set(names)):
        raise ReleaseGateError("zip", "ZIP contains duplicate member names.")
    for name in names:
        path = PurePosixPath(name)
        if (
            not name
            or "\\" in name
            or path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
            or ":" in path.parts[0]
        ):
            raise ReleaseGateError("zip", f"Unsafe ZIP member name: {name!r}.")
    _validate_kit_inventory(set(names), expected_names)


def _build_manifest(
    *,
    product_name: str,
    package_version: str,
    source_head_sha: str,
    source_tree_clean_at_build_start: bool,
    certification_mode: str,
    python_version: str,
    uv_version: str,
    build_backend: str,
    build_requirements: list[str],
    wheel_filename: str,
    file_hashes: dict[str, str],
    ffmpeg_version: str,
    ffprobe_version: str,
) -> dict[str, Any]:
    companion_names = sorted(name for name in file_hashes if name != wheel_filename)
    development = certification_mode == "development"
    artifact_set_claim = (
        "This manifest identifies a non-certifying development candidate and records "
        "the source HEAD SHA and working-tree state observed at build start; uncommitted "
        "changes may be present."
        if development
        else "This manifest identifies a strict certification candidate built from a source "
        "tree that was clean at build start at the recorded HEAD SHA; certification is "
        "authoritative only when the final verification report passes."
    )
    return {
        "manifest_schema_version": "1.0",
        "product_name": product_name,
        "package_version": package_version,
        "source": {
            "head_sha_at_build_start": source_head_sha,
            "tree_clean_at_build_start": source_tree_clean_at_build_start,
        },
        "certification_mode": certification_mode,
        "candidate_nature": (
            "non-certifying development candidate"
            if development
            else "strict certification candidate"
        ),
        "supported_platform": {
            "operating_system": "Windows 11",
            "architecture": "x64",
            "execution": "CPU-only",
        },
        "python": {
            "target": "3.12",
            "verification_version": python_version,
        },
        "build": {
            "uv_version": uv_version,
            "backend": build_backend,
            "backend_requirements": build_requirements,
        },
        "wheel": {
            "filename": wheel_filename,
            "sha256": file_hashes[wheel_filename],
        },
        "runtime_constraints": {
            "filename": "runtime-constraints.txt",
            "sha256": file_hashes["runtime-constraints.txt"],
            "source": "mechanically exported from uv.lock",
        },
        "required_companion_files": [
            {"path": name, "sha256": file_hashes[name]} for name in companion_names
        ],
        "covered_files": [
            {"path": name, "sha256": file_hashes[name]} for name in sorted(file_hashes)
        ],
        "release_notes": {
            "path": "CHANGELOG.md",
            "canonical_source": "docs/CHANGELOG.md",
            "source_head_sha_at_build_start": source_head_sha,
        },
        "external_media_tools": {
            "ffmpeg": {"version": ffmpeg_version},
            "ffprobe": {"version": ffprobe_version},
            "bundled": False,
        },
        "release_gate": {
            "tool": "verify_stage10_release.py",
            "tool_version": _TOOL_VERSION,
        },
        "hash_algorithm": "SHA-256",
        "artifact_set_claim": artifact_set_claim,
        "manifest_self_hash": None,
    }


def _run_command(
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: float,
    phase: str,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            cwd=cwd,
            env=env,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise ReleaseGateError(phase, f"Command exceeded its {timeout:g}s deadline.") from None
    except subprocess.CalledProcessError as error:
        output = "\n".join(part for part in (error.stdout, error.stderr) if part)
        safe_tail = output[-4000:]
        raise ReleaseGateError(
            phase,
            f"Command failed with return code {error.returncode}: {safe_tail}",
            process_returncode=error.returncode,
        ) from None
    except OSError:
        raise ReleaseGateError(phase, "Command could not be started.") from None


def _sanitized_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("FAKEDETECTOR_")
    }
    for name in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
        environment.pop(name, None)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PIP_CONFIG_FILE"] = os.devnull
    return environment


def _prepare_output_directory(requested: Path | None, repository: Path) -> Path:
    if requested is None:
        output = Path(tempfile.mkdtemp(prefix="fakedetector-stage10-release-")).resolve()
    else:
        output = requested.expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        if any(output.iterdir()):
            raise ReleaseGateError("output", "Requested output directory must be empty.")
    if output == repository or repository in output.parents:
        raise ReleaseGateError("output", "Release output must be outside the repository.")
    return output


def _copy_new(source: Path, destination: Path) -> None:
    try:
        with source.open("rb") as input_stream, destination.open("xb") as output_stream:
            shutil.copyfileobj(input_stream, output_stream)
    except OSError:
        raise ReleaseGateError("release_kit", "A release-kit file could not be copied.") from None


def _probe_external_tool(
    executable_name: str,
    *,
    cwd: Path,
    env: dict[str, str],
) -> str:
    executable = shutil.which(executable_name, path=env.get("PATH"))
    if executable is None:
        raise ReleaseGateError("prerequisites", f"{executable_name} is not available on PATH.")
    completed = _run_command(
        [executable, "-version"],
        cwd=cwd,
        env=env,
        timeout=10.0,
        phase="prerequisites",
    )
    version_line = next(
        (line.strip() for line in completed.stdout.splitlines() if line.strip()),
        "",
    )
    if not version_line:
        raise ReleaseGateError("prerequisites", f"{executable_name} returned no version evidence.")
    return version_line


def _build_release_inputs(
    *,
    repository: Path,
    output: Path,
    project_name: str,
    uv: str,
    env: dict[str, str],
) -> dict[str, Any]:
    artifacts = output / "build" / "artifacts"
    artifacts.mkdir(parents=True)
    _run_command(
        [
            uv,
            "build",
            "--sdist",
            "--no-create-gitignore",
            "--out-dir",
            str(artifacts),
            str(repository),
        ],
        cwd=output,
        env=env,
        timeout=_PHASE_TIMEOUTS["build"],
        phase="build_sdist",
    )
    try:
        sdist = package_verifier._single_artifact(artifacts, f"{project_name}-*.tar.gz")
    except package_verifier.VerificationError as error:
        raise ReleaseGateError("build_sdist", str(error)) from None
    _run_command(
        [
            uv,
            "build",
            "--wheel",
            "--no-create-gitignore",
            "--out-dir",
            str(artifacts),
            str(sdist),
        ],
        cwd=output,
        env=env,
        timeout=_PHASE_TIMEOUTS["build"],
        phase="build_wheel",
    )
    try:
        wheel = package_verifier._single_artifact(artifacts, f"{project_name}-*.whl")
    except package_verifier.VerificationError as error:
        raise ReleaseGateError("build_wheel", str(error)) from None

    constraints = output / "build" / "runtime-constraints.txt"
    constraints_command = [
        uv,
        "export",
        "--locked",
        "--no-dev",
        "--no-emit-project",
        "--format",
        "requirements.txt",
        "--no-annotate",
        "--no-header",
        "--no-hashes",
        "--output-file",
        str(constraints),
    ]
    _run_command(
        constraints_command,
        cwd=repository,
        env=env,
        timeout=_PHASE_TIMEOUTS["constraints"],
        phase="constraints",
    )
    return {
        "sdist": sdist,
        "wheel": wheel,
        "constraints": constraints,
        "constraints_command": subprocess.list2cmdline(constraints_command),
    }


def _assemble_release_kit(
    *,
    repository: Path,
    output: Path,
    project_name: str,
    wheel: Path,
    constraints: Path,
    manifest_arguments: dict[str, Any],
) -> tuple[Path, dict[str, Any], str, dict[str, str]]:
    kit = output / f"{project_name}-{manifest_arguments['package_version']}"
    kit.mkdir()
    _copy_new(wheel, kit / wheel.name)
    _copy_new(constraints, kit / "runtime-constraints.txt")
    for destination_name, relative_source in _COMPANION_SOURCES.items():
        _copy_new(repository / relative_source, kit / destination_name)

    file_hashes = {
        path.name: _sha256_file(path)
        for path in kit.iterdir()
        if path.is_file() and path.name != _MANIFEST_NAME
    }
    manifest = _build_manifest(
        wheel_filename=wheel.name,
        file_hashes=file_hashes,
        **manifest_arguments,
    )
    manifest_path = kit / _MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    expected_names = _expected_kit_names(wheel.name)
    actual_names = {path.name for path in kit.iterdir() if path.is_file()}
    _validate_kit_inventory(actual_names, expected_names)
    if any(path.is_dir() for path in kit.iterdir()):
        raise ReleaseGateError("release_kit", "Release kit contains an unexpected directory.")
    return kit, manifest, _sha256_file(manifest_path), file_hashes


def _create_zip(kit: Path, zip_path: Path, expected_names: set[str]) -> None:
    with zipfile.ZipFile(zip_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(expected_names):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (kit / name).read_bytes())


def _verify_zip(
    *,
    zip_path: Path,
    output: Path,
    expected_names: set[str],
    manifest: dict[str, Any],
    manifest_sha256: str,
) -> tuple[Path, dict[str, Any]]:
    extraction = output / "verified-zip-extraction"
    extraction.mkdir()
    manifest_hashes = {item["path"]: item["sha256"] for item in manifest["covered_files"]}
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        _validate_zip_member_names(names, expected_names)
        for name in names:
            payload = archive.read(name)
            if name == _MANIFEST_NAME:
                if _sha256_bytes(payload) != manifest_sha256:
                    raise ReleaseGateError("zip", "Manifest bytes differ inside the ZIP.")
            elif _sha256_bytes(payload) != manifest_hashes.get(name):
                raise ReleaseGateError("zip", f"ZIP hash mismatch for {name}.")
            target = extraction / name
            with target.open("xb") as stream:
                stream.write(payload)
    extracted_manifest = json.loads((extraction / _MANIFEST_NAME).read_text(encoding="utf-8"))
    if extracted_manifest != manifest:
        raise ReleaseGateError("zip", "Extracted manifest differs semantically.")
    for name, expected_hash in manifest_hashes.items():
        if _sha256_file(extraction / name) != expected_hash:
            raise ReleaseGateError("zip", f"Extracted file hash mismatch for {name}.")
    return extraction, {
        "status": "passed",
        "safe_member_names": True,
        "inventory_match": True,
        "hashes_match": True,
        "clean_extraction": True,
        "entry_count": len(expected_names),
    }


def _installed_probe(
    python: Path,
    *,
    cwd: Path,
    env: dict[str, str],
    project_name: str,
) -> dict[str, Any]:
    probe = textwrap.dedent(
        f"""
        import importlib.metadata as metadata
        import importlib.resources as resources
        import json
        import os
        import platform
        import sys
        from pathlib import Path

        import fakedetector

        distribution = metadata.distribution({project_name!r})
        direct_url_text = distribution.read_text("direct_url.json")
        resource_root = resources.files("fakedetector")
        resources_found = {{
            name: resource_root.joinpath(name).is_file()
            for name in {list(package_verifier._REQUIRED_RESOURCES)!r}
        }}
        installed = {{
            item.metadata["Name"]: item.version
            for item in metadata.distributions()
            if item.metadata["Name"]
        }}
        implementation = sys.implementation.version
        marker_environment = {{
            "implementation_name": sys.implementation.name,
            "implementation_version": ".".join(str(part) for part in (
                implementation.major, implementation.minor, implementation.micro
            )),
            "os_name": os.name,
            "platform_machine": platform.machine(),
            "platform_python_implementation": platform.python_implementation(),
            "platform_release": platform.release(),
            "platform_system": platform.system(),
            "platform_version": platform.version(),
            "python_full_version": platform.python_version(),
            "python_version": ".".join(platform.python_version_tuple()[:2]),
            "sys_platform": sys.platform,
            "extra": "",
        }}
        print(json.dumps({{
            "package_version": distribution.version,
            "module_version": fakedetector.__version__,
            "module_origin": str(Path(fakedetector.__file__).resolve()),
            "direct_url": json.loads(direct_url_text) if direct_url_text else None,
            "resources": resources_found,
            "installed": installed,
            "marker_environment": marker_environment,
            "python_version": platform.python_version(),
            "sys_path": sys.path,
            "user_site_enabled": bool(__import__("site").ENABLE_USER_SITE),
        }}, sort_keys=True))
        """
    )
    completed = _run_command(
        [str(python), "-I", "-c", probe],
        cwd=cwd,
        env=env,
        timeout=_PHASE_TIMEOUTS["probe"],
        phase="installed_probe",
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        raise ReleaseGateError(
            "installed_probe", "Installed probe returned invalid JSON."
        ) from None
    if not isinstance(payload, dict):
        raise ReleaseGateError("installed_probe", "Installed probe returned an invalid value.")
    return payload


def _create_and_verify_venv(
    *,
    repository: Path,
    output: Path,
    extraction: Path,
    wheel_filename: str,
    uv: str,
    env: dict[str, str],
    project_name: str,
    project_version: str,
) -> tuple[Path, Path, dict[str, Any]]:
    venv = output / "installed-venv"
    _run_command(
        [uv, "venv", "--python", "3.12", "--no-project", str(venv)],
        cwd=output,
        env=env,
        timeout=_PHASE_TIMEOUTS["venv"],
        phase="venv",
    )
    scripts = venv / ("Scripts" if os.name == "nt" else "bin")
    python = scripts / ("python.exe" if os.name == "nt" else "python")
    cli = scripts / (f"{project_name}.exe" if os.name == "nt" else project_name)
    wheel = extraction / wheel_filename
    constraints = extraction / "runtime-constraints.txt"
    _run_command(
        [
            uv,
            "pip",
            "install",
            "--python",
            str(python),
            "--constraint",
            str(constraints),
            str(wheel),
        ],
        cwd=output,
        env=env,
        timeout=_PHASE_TIMEOUTS["install"],
        phase="install",
    )
    _run_command(
        [uv, "pip", "check", "--python", str(python)],
        cwd=output,
        env=env,
        timeout=_PHASE_TIMEOUTS["probe"],
        phase="dependency_check",
    )
    probe = _installed_probe(python, cwd=output, env=env, project_name=project_name)

    if probe["package_version"] != project_version or probe["module_version"] != project_version:
        raise ReleaseGateError("installed_probe", "Installed version differs from build metadata.")
    if not probe["python_version"].startswith("3.12."):
        raise ReleaseGateError("installed_probe", "Fresh venv is not running Python 3.12.")
    if probe["user_site_enabled"]:
        raise ReleaseGateError("installed_probe", "Fresh venv unexpectedly enables user site.")
    if not all(probe["resources"].values()):
        raise ReleaseGateError("installed_probe", "Installed package resources are incomplete.")

    module_origin = Path(probe["module_origin"]).resolve()
    if venv.resolve() not in module_origin.parents or "site-packages" not in {
        part.casefold() for part in module_origin.parts
    }:
        raise ReleaseGateError("installed_probe", "Package did not import from venv site-packages.")
    repository_resolved = repository.resolve()
    checkout_on_sys_path = any(
        candidate == repository_resolved or repository_resolved in candidate.parents
        for raw_path in probe["sys_path"]
        if raw_path
        for candidate in [Path(raw_path).resolve()]
    )
    if repository_resolved in module_origin.parents or checkout_on_sys_path:
        raise ReleaseGateError("installed_probe", "Source checkout leaked into installed runtime.")
    direct_url = probe["direct_url"]
    if not isinstance(direct_url, dict) or direct_url.get("url") != wheel.as_uri():
        raise ReleaseGateError(
            "installed_probe", "Installed project is not bound to ZIP wheel bytes."
        )
    if direct_url.get("dir_info", {}).get("editable", False):
        raise ReleaseGateError("installed_probe", "Editable installation is forbidden.")

    try:
        expected = package_verifier._parse_constraints(constraints, probe["marker_environment"])
        comparison = package_verifier._assert_runtime_matches_constraints(
            installed=probe["installed"],
            expected=expected,
            direct_dev_names=package_verifier._direct_dev_names(repository / "pyproject.toml"),
        )
    except package_verifier.VerificationError as error:
        raise ReleaseGateError("dependency_comparison", str(error)) from None
    help_result = _run_command(
        [str(cli), "--help"],
        cwd=output,
        env=env,
        timeout=_PHASE_TIMEOUTS["probe"],
        phase="cli_help",
    )
    if "usage:" not in help_result.stdout.casefold():
        raise ReleaseGateError("cli_help", "Installed CLI help lacks argparse usage.")
    return (
        python,
        cli,
        {
            "python_version": probe["python_version"],
            "installed_origin": probe["module_origin"],
            "editable_install": False,
            "source_checkout_on_sys_path": False,
            "user_site_enabled": False,
            "installed_from_zip_wheel": True,
            "dependency_check": "passed",
            "runtime_dependency_comparison": comparison,
            "installed_resources": sorted(
                name for name, present in probe["resources"].items() if present
            ),
        },
    )


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
            "sha256": _sha256_file(image_path),
        }
    if not (
        image_evidence["format"] == "PNG"
        and image_evidence["mode"] == "RGB"
        and (image_evidence["width"], image_evidence["height"]) == (512, 512)
        and repeated_region
    ):
        raise ReleaseGateError("demo", "Generated PNG properties are invalid.")

    audio_path = media[".wav"]
    with wave.open(str(audio_path), "rb") as audio:
        audio_evidence = {
            "filename": audio_path.name,
            "channels": audio.getnchannels(),
            "sample_width_bytes": audio.getsampwidth(),
            "sample_rate_hz": audio.getframerate(),
            "frame_count": audio.getnframes(),
            "compression": audio.getcomptype(),
            "sha256": _sha256_file(audio_path),
        }
    if (
        audio_evidence["channels"],
        audio_evidence["sample_width_bytes"],
        audio_evidence["sample_rate_hz"],
        audio_evidence["frame_count"],
        audio_evidence["compression"],
    ) != (1, 2, 8000, 8000, "NONE"):
        raise ReleaseGateError("demo", "Generated WAV properties are invalid.")

    ffprobe = shutil.which("ffprobe", path=env.get("PATH"))
    if ffprobe is None:
        raise ReleaseGateError("demo", "ffprobe disappeared from PATH.")
    video_path = media[".mp4"]
    completed = _run_command(
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
        raise ReleaseGateError("demo", "Generated MP4 probe is invalid.") from None
    video_evidence = {
        "filename": video_path.name,
        "codec_type": stream.get("codec_type"),
        "width": stream.get("width"),
        "height": stream.get("height"),
        "frame_rate": stream.get("r_frame_rate"),
        "duration_seconds": duration,
        "sha256": _sha256_file(video_path),
    }
    if not (
        video_evidence["codec_type"] == "video"
        and (video_evidence["width"], video_evidence["height"]) == (64, 64)
        and video_evidence["frame_rate"] == "2/1"
        and 3.0 <= duration <= 4.0
    ):
        raise ReleaseGateError("demo", "Generated MP4 properties are invalid.")
    return {"image": image_evidence, "audio": audio_evidence, "video": video_evidence}


def _generate_demo_media(
    *,
    python: Path,
    extraction: Path,
    work: Path,
    env: dict[str, str],
) -> tuple[dict[str, Path], dict[str, Any]]:
    output = work / "demo-media"
    generator = extraction / "generate_stage10_demo_media.py"
    command = [str(python), str(generator), "--output-dir", str(output)]
    _run_command(
        command,
        cwd=work,
        env=env,
        timeout=_PHASE_TIMEOUTS["demo"],
        phase="demo",
    )
    media = {suffix: output / name for suffix, name in _DEMO_NAMES.items()}
    if not all(path.is_file() for path in media.values()):
        raise ReleaseGateError("demo", "Release-kit generator did not create all demo files.")
    evidence = _probe_demo_media(media, env=env)
    evidence["generation"] = {
        "status": "passed",
        "generator_source": "verified ZIP extraction",
        "python": "fresh installed environment",
    }
    return media, evidence


def _reserve_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _profile_b_ids(raw: dict[str, Any]) -> dict[str, list[str]]:
    return {
        media: list(raw["analyzers"][media]["enabled"]) for media in ("image", "audio", "video")
    }


def _prepare_work_config(
    *,
    extraction: Path,
    work: Path,
    port: int,
    secret_values: tuple[str, ...],
) -> tuple[Path, dict[str, Any]]:
    raw = yaml.safe_load((extraction / "config.example.yaml").read_text(encoding="utf-8"))
    expected_profile = {
        "image": ["image_metadata_consistency", "image_copy_move_correspondence"],
        "audio": ["audio_pcm_quality"],
        "video": ["video_sampled_frame_quality"],
    }
    if _profile_b_ids(raw) != expected_profile:
        raise ReleaseGateError("work_config", "Release-kit config is not canonical Profile B.")
    raw["server"]["host"] = "127.0.0.1"
    raw["server"]["port"] = port
    raw["temporary_storage"]["root_path"] = str((work / "runtime" / "temp").resolve())
    raw["result"]["directory"] = str((work / "runtime" / "results").resolve())
    raw["logging"]["jsonl_path"] = str((work / "runtime" / "logs" / "application.jsonl").resolve())
    raw["limits"]["max_parallel_tasks"] = {"image": 1, "audio": 1, "video": 1}
    raw["limits"]["processing_timeout_seconds"] = 120
    raw["analyzers"]["defaults"]["timeout_seconds"] = 60
    rendered = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    if any(secret_value and secret_value in rendered for secret_value in secret_values):
        raise ReleaseGateError("work_config", "A generated secret entered the work config.")
    config_path = work / "config.yaml"
    config_path.write_text(rendered, encoding="utf-8")
    return config_path, raw


def _rewrite_config_port(config_path: Path, raw: dict[str, Any], port: int) -> None:
    raw["server"]["port"] = port
    config_path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _http_exchange(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: float = 5.0,
) -> tuple[int, dict[str, str], bytes]:
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    request = Request(url, data=data, headers=headers or {}, method=method)
    try:
        response = opener.open(request, timeout=timeout)
    except HTTPError as error:
        response = error
    except URLError as error:
        reason = error.reason
        if isinstance(reason, OSError):
            raise reason from error
        raise OSError("loopback request failed") from None
    with response:
        payload = response.read(_MAX_HTTP_BODY_BYTES + 1)
        if len(payload) > _MAX_HTTP_BODY_BYTES:
            raise ReleaseGateError("http", "HTTP response exceeded the gate bound.")
        return (
            int(response.status),
            {name.casefold(): value for name, value in response.headers.items()},
            payload,
        )


def _require_http(
    method: str,
    url: str,
    *,
    expected_status: int,
    phase: str,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: float = 10.0,
) -> tuple[dict[str, str], bytes]:
    try:
        status, response_headers, body = _http_exchange(
            method,
            url,
            headers=headers,
            data=data,
            timeout=timeout,
        )
    except OSError:
        raise ReleaseGateError(phase, "Loopback HTTP request failed.") from None
    if status != expected_status:
        raise ReleaseGateError(
            phase,
            f"Expected HTTP {expected_status}, received HTTP {status}.",
        )
    return response_headers, body


def _json_object(body: bytes, *, phase: str) -> dict[str, Any]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise ReleaseGateError(phase, "HTTP response is not valid JSON.") from None
    if not isinstance(payload, dict):
        raise ReleaseGateError(phase, "HTTP response JSON is not an object.")
    return payload


def _multipart(path: Path, mime: str) -> tuple[bytes, str]:
    boundary = f"fakedetector-stage10-{secrets.token_hex(12)}"
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("ascii")
    body = header + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("ascii")
    return body, f"multipart/form-data; boundary={boundary}"


def _spawn_server(
    *,
    cli: Path,
    config_path: Path,
    work: Path,
    env: dict[str, str],
    port: int,
) -> _ServerProcess:
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    try:
        process = subprocess.Popen(
            [str(cli), "--config", str(config_path)],
            cwd=work,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creationflags,
            start_new_session=os.name != "nt",
        )
    except OSError:
        raise ReleaseGateError("startup", "Installed CLI process could not be started.") from None
    return _ServerProcess(process, port)


def _wait_for_health(
    server: _ServerProcess,
    *,
    secret_values: tuple[str, ...],
) -> dict[str, Any]:
    deadline = time.monotonic() + _PHASE_TIMEOUTS["startup"]
    url = f"http://127.0.0.1:{server.port}/health"
    last_transport_error: str | None = None
    while time.monotonic() < deadline:
        returncode = server.process.poll()
        if returncode is not None:
            server.join_readers()
            raise ReleaseGateError(
                "startup",
                "Installed CLI exited before health readiness.",
                process_returncode=returncode,
                server_output_tail=server.output_tail(secret_values),
            )
        try:
            status, _headers, body = _http_exchange("GET", url, timeout=0.5)
        except OSError as error:
            last_transport_error = type(error).__name__
            time.sleep(0.05)
            continue
        if status != 200 or _json_object(body, phase="health") != {"status": "ok"}:
            raise ReleaseGateError("health", "Health endpoint returned an invalid response.")
        if server.process.poll() is not None:
            raise ReleaseGateError("health", "Installed CLI exited during health readiness.")
        return {"status": "passed", "http_status": 200, "payload": {"status": "ok"}}
    raise ReleaseGateError(
        "startup",
        f"Health readiness exceeded deadline; last transport error={last_transport_error}.",
        process_returncode=server.process.poll(),
        server_output_tail=server.output_tail(secret_values),
    )


def _is_bind_failure(output: str) -> bool:
    normalized = output.casefold()
    return any(
        marker in normalized
        for marker in (
            "address already in use",
            "only one usage of each socket address",
            "winerror 10048",
            "errno 10048",
            "eaddrinuse",
        )
    )


def _emergency_stop(server: _ServerProcess) -> None:
    process = server.process
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5.0)
    server.join_readers()


def _start_server_with_bind_retry(
    *,
    cli: Path,
    config_path: Path,
    config_raw: dict[str, Any],
    work: Path,
    env: dict[str, str],
    secret_values: tuple[str, ...],
    attempts: int = 3,
) -> tuple[_ServerProcess, dict[str, Any]]:
    for attempt in range(1, attempts + 1):
        port = _reserve_loopback_port()
        _rewrite_config_port(config_path, config_raw, port)
        server = _spawn_server(
            cli=cli,
            config_path=config_path,
            work=work,
            env=env,
            port=port,
        )
        try:
            health = _wait_for_health(server, secret_values=secret_values)
        except ReleaseGateError as error:
            tail = server.output_tail(secret_values)
            returncode = server.process.poll()
            if returncode is not None:
                server.join_readers()
            else:
                _emergency_stop(server)
            if attempt < attempts and returncode is not None and _is_bind_failure(tail):
                continue
            if error.server_output_tail is None:
                error.server_output_tail = tail
            raise
        return server, {
            "status": "passed",
            "attempts": attempt,
            "dynamic_loopback_port": port,
            "health": health,
        }
    raise ReleaseGateError("startup", "Bounded bind retry was exhausted.")


def _start_server_same_config(
    *,
    cli: Path,
    config_path: Path,
    work: Path,
    env: dict[str, str],
    port: int,
    secret_values: tuple[str, ...],
) -> tuple[_ServerProcess, dict[str, Any]]:
    server = _spawn_server(
        cli=cli,
        config_path=config_path,
        work=work,
        env=env,
        port=port,
    )
    try:
        health = _wait_for_health(server, secret_values=secret_values)
    except ReleaseGateError:
        _emergency_stop(server)
        raise
    return server, {
        "status": "passed",
        "attempts": 1,
        "loopback_port": port,
        "health": health,
    }


def _listener_closed(port: int, *, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                time.sleep(0.05)
        except OSError:
            return True
    return False


def _graceful_shutdown(
    server: _ServerProcess,
    *,
    secret_values: tuple[str, ...],
) -> dict[str, Any]:
    process = server.process
    if process.poll() is not None:
        server.join_readers()
        raise ReleaseGateError(
            "shutdown",
            "Server exited before graceful shutdown was initiated.",
            process_returncode=process.returncode,
            server_output_tail=server.output_tail(secret_values),
        )
    try:
        if os.name == "nt":
            os.kill(process.pid, signal.CTRL_BREAK_EVENT)
            signal_method = "CTRL_BREAK_EVENT"
        else:
            process.send_signal(signal.SIGINT)
            signal_method = "SIGINT"
        process.wait(timeout=_PHASE_TIMEOUTS["shutdown"])
    except (OSError, subprocess.TimeoutExpired):
        _emergency_stop(server)
        raise ReleaseGateError(
            "shutdown",
            "Graceful shutdown did not complete before the deadline.",
            process_returncode=process.poll(),
            server_output_tail=server.output_tail(secret_values),
        ) from None
    server.join_readers()
    output = server.output_tail(secret_values)
    normalized = output.casefold()
    marker_evidence = {
        "shutdown_started": "shutting down" in normalized,
        "lifespan_shutdown_completed": "application shutdown complete" in normalized,
        "server_finished": "finished server process" in normalized,
    }
    listener_closed = _listener_closed(server.port)
    if not all(marker_evidence.values()) or not listener_closed or process.poll() is None:
        raise ReleaseGateError(
            "shutdown",
            "Signal-aware graceful shutdown evidence is incomplete.",
            process_returncode=process.poll(),
            server_output_tail=output,
        )
    return {
        "status": "passed",
        "signal": signal_method,
        "returncode": process.returncode,
        "markers": marker_evidence,
        "listener_closed": listener_closed,
        "process_reaped": True,
    }


def _basic_header(username: str, password: str) -> str:
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    return f"Basic {encoded}"


def _auth_headers_and_redaction_values(
    *,
    api_token: str,
    webui_username: str,
    webui_password: str,
) -> tuple[str, str, str, tuple[str, ...]]:
    basic_credentials = f"{webui_username}:{webui_password}"
    basic_header = _basic_header(webui_username, webui_password)
    basic_payload = basic_header.removeprefix("Basic ")
    bearer_header = f"Bearer {api_token}"
    secret_values = (
        api_token,
        webui_username,
        webui_password,
        basic_credentials,
        basic_payload,
        basic_header,
        bearer_header,
    )
    return basic_credentials, basic_header, bearer_header, secret_values


def _poll_api_result(
    *,
    base_url: str,
    analysis_id: str,
    bearer_header: str,
) -> dict[str, Any]:
    deadline = time.monotonic() + _PHASE_TIMEOUTS["analysis"]
    url = f"{base_url}/api/v1/analyses/{analysis_id}/result"
    while time.monotonic() < deadline:
        try:
            status, _headers, body = _http_exchange(
                "GET",
                url,
                headers={"Authorization": bearer_header},
                timeout=2.0,
            )
        except OSError:
            raise ReleaseGateError(
                "analysis",
                "Loopback result polling failed.",
                analysis_id=analysis_id,
            ) from None
        if status == 200:
            return _json_object(body, phase="analysis")
        if status != 202:
            raise ReleaseGateError(
                "analysis",
                f"Result polling returned HTTP {status}.",
                analysis_id=analysis_id,
            )
        time.sleep(0.1)
    raise ReleaseGateError(
        "analysis",
        "Analysis polling exceeded its deadline.",
        analysis_id=analysis_id,
    )


def _validate_result(
    *,
    result: dict[str, Any],
    analysis_id: str,
    suffix: str,
    expected_application_version: str,
) -> dict[str, Any]:
    expected_analyzers = _EXPECTED_ANALYZERS[suffix]
    actual_analyzers = tuple(
        (item.get("analyzer_id"), item.get("analyzer_version"))
        for item in result.get("analyzers", [])
    )
    checks = {
        "schema_version": result.get("schema_version") == "1.0",
        "analysis_id": result.get("analysis_id") == analysis_id,
        "status": result.get("status") == "completed",
        "stage": result.get("stage") == "finished",
        "completeness": result.get("completeness", {}).get("status") == "complete",
        "analyzers": actual_analyzers == expected_analyzers,
        "analyzer_statuses": all(
            item.get("status") == "completed" for item in result.get("analyzers", [])
        ),
        "risk_present": isinstance(result.get("risk_assessment"), dict)
        and result["risk_assessment"].get("final_level") is not None,
        "recommendation_present": isinstance(result.get("recommendation"), dict)
        and bool(result["recommendation"].get("text")),
        "cleanup": result.get("cleanup", {}).get("status") == "completed",
        "application_version": result.get("processing", {}).get("application_version")
        == expected_application_version,
    }
    if not all(checks.values()):
        raise ReleaseGateError(
            "analysis",
            "Terminal result failed structural validation: " + json.dumps(checks, sort_keys=True),
            analysis_id=analysis_id,
        )
    return {
        "status": "passed",
        "analysis_id": analysis_id,
        "terminal_status": result["status"],
        "completeness_status": result["completeness"]["status"],
        "analyzers": [
            {"analyzer_id": analyzer_id, "analyzer_version": analyzer_version}
            for analyzer_id, analyzer_version in actual_analyzers
        ],
        "risk_present": True,
        "recommendation_present": True,
        "cleanup_status": result["cleanup"]["status"],
        "schema_version": result["schema_version"],
    }


def _verify_persistence_and_cleanup(
    *,
    result: dict[str, Any],
    analysis_id: str,
    config_raw: dict[str, Any],
) -> dict[str, Any]:
    result_path = Path(config_raw["result"]["directory"]) / f"{analysis_id}.json"
    if not result_path.is_file():
        raise ReleaseGateError(
            "persistence", "Canonical result file is missing.", analysis_id=analysis_id
        )
    try:
        persisted = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise ReleaseGateError(
            "persistence", "Canonical result file is unreadable.", analysis_id=analysis_id
        ) from None
    if persisted != result:
        raise ReleaseGateError(
            "persistence",
            "HTTP result differs from canonical persisted JSON.",
            analysis_id=analysis_id,
        )
    temp_root = Path(config_raw["temporary_storage"]["root_path"])
    workspace_absent = not (temp_root / analysis_id).exists()
    quarantine_absent = not (temp_root.parent / "quarantine" / analysis_id).exists()
    if not workspace_absent or not quarantine_absent:
        raise ReleaseGateError(
            "cleanup", "Analysis workspace or quarantine residue remains.", analysis_id=analysis_id
        )
    return {
        "analysis_id": analysis_id,
        "canonical_result": result_path.name,
        "semantic_match": True,
        "workspace_absent": True,
        "quarantine_residue_absent": True,
    }


def _submit_api_analysis(
    *,
    base_url: str,
    path: Path,
    bearer_header: str,
    config_raw: dict[str, Any],
    expected_application_version: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    body, content_type = _multipart(path, _MEDIA_MIME[path.suffix])
    _headers, response_body = _require_http(
        "POST",
        f"{base_url}/api/v1/analyses",
        expected_status=202,
        phase="api_upload",
        headers={
            "Authorization": bearer_header,
            "Content-Type": content_type,
        },
        data=body,
        timeout=30.0,
    )
    submission = _json_object(response_body, phase="api_upload")
    analysis_id = submission.get("analysis_id")
    if not isinstance(analysis_id, str) or not analysis_id:
        raise ReleaseGateError("api_upload", "Submission lacks analysis_id.")
    result = _poll_api_result(
        base_url=base_url,
        analysis_id=analysis_id,
        bearer_header=bearer_header,
    )
    evidence = _validate_result(
        result=result,
        analysis_id=analysis_id,
        suffix=path.suffix,
        expected_application_version=expected_application_version,
    )
    _status_headers, status_body = _require_http(
        "GET",
        f"{base_url}/api/v1/analyses/{analysis_id}",
        expected_status=200,
        phase="api_status",
        headers={"Authorization": bearer_header},
    )
    status_payload = _json_object(status_body, phase="api_status")
    if not status_payload.get("result_available"):
        raise ReleaseGateError(
            "api_status", "Completed result is not marked available.", analysis_id=analysis_id
        )
    persistence = _verify_persistence_and_cleanup(
        result=result,
        analysis_id=analysis_id,
        config_raw=config_raw,
    )
    return result, evidence, persistence


def _exercise_webui(
    *,
    base_url: str,
    image_path: Path,
    basic_header: str,
    bearer_header: str,
    config_raw: dict[str, Any],
    expected_application_version: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    unauth_headers, _unauth_body = _require_http(
        "GET", base_url + "/", expected_status=401, phase="webui_auth"
    )
    if "basic" not in unauth_headers.get("www-authenticate", "").casefold():
        raise ReleaseGateError("webui_auth", "WebUI challenge lacks Basic scheme.")
    _root_headers, root_body = _require_http(
        "GET",
        base_url + "/",
        expected_status=200,
        phase="webui",
        headers={"Authorization": basic_header},
    )
    if b"FakeDetector" not in root_body:
        raise ReleaseGateError("webui", "Authenticated upload page is invalid.")
    css_headers, css_body = _require_http(
        "GET",
        base_url + "/static/styles.css",
        expected_status=200,
        phase="webui_static",
        headers={"Authorization": basic_header},
    )
    if not css_body or "text/css" not in css_headers.get("content-type", ""):
        raise ReleaseGateError("webui_static", "Required CSS asset is invalid.")

    multipart_body, content_type = _multipart(image_path, _MEDIA_MIME[image_path.suffix])
    upload_headers, _upload_body = _require_http(
        "POST",
        base_url + "/analyses",
        expected_status=303,
        phase="webui_upload",
        headers={
            "Authorization": basic_header,
            "Origin": base_url,
            "Content-Type": content_type,
        },
        data=multipart_body,
        timeout=30.0,
    )
    status_location = upload_headers.get("location")
    if not status_location:
        raise ReleaseGateError("webui_upload", "WebUI upload lacks status redirect.")
    analysis_id = status_location.rstrip("/").rsplit("/", maxsplit=1)[-1]
    status_url = urljoin(base_url, status_location)
    deadline = time.monotonic() + _PHASE_TIMEOUTS["analysis"]
    result_location: str | None = None
    while time.monotonic() < deadline:
        try:
            status, response_headers, _body = _http_exchange(
                "GET",
                status_url,
                headers={"Authorization": basic_header},
                timeout=2.0,
            )
        except OSError:
            raise ReleaseGateError(
                "webui_upload", "WebUI status polling failed.", analysis_id=analysis_id
            ) from None
        if status == 303:
            result_location = response_headers.get("location")
            break
        if status != 200:
            raise ReleaseGateError(
                "webui_upload",
                f"WebUI status returned HTTP {status}.",
                analysis_id=analysis_id,
            )
        time.sleep(0.1)
    if result_location is None:
        raise ReleaseGateError(
            "webui_upload", "WebUI analysis exceeded its deadline.", analysis_id=analysis_id
        )
    _result_headers, result_page = _require_http(
        "GET",
        urljoin(base_url, result_location),
        expected_status=200,
        phase="webui_result",
        headers={"Authorization": basic_header},
    )
    if analysis_id.encode() not in result_page or "Результат анализа".encode() not in result_page:
        raise ReleaseGateError(
            "webui_result", "WebUI result page is invalid.", analysis_id=analysis_id
        )
    result = _poll_api_result(
        base_url=base_url,
        analysis_id=analysis_id,
        bearer_header=bearer_header,
    )
    evidence = _validate_result(
        result=result,
        analysis_id=analysis_id,
        suffix=".png",
        expected_application_version=expected_application_version,
    )
    persistence = _verify_persistence_and_cleanup(
        result=result,
        analysis_id=analysis_id,
        config_raw=config_raw,
    )
    webui = {
        "status": "passed",
        "unauthenticated_status": 401,
        "basic_authenticated_root": 200,
        "css_status": 200,
        "upload_status": 303,
        "same_origin_header": "Origin",
        "analysis_id": analysis_id,
        "status_redirect": 303,
        "result_status": 200,
    }
    return result, evidence, persistence, webui


def _exercise_api_auth(base_url: str, bearer_header: str) -> dict[str, Any]:
    for label, headers in (
        ("missing", {}),
        ("invalid", {"Authorization": "Bearer invalid-release-gate-token"}),
    ):
        _response_headers, body = _require_http(
            "GET",
            f"{base_url}/api/v1/analyses/unknown",
            expected_status=401,
            phase="api_auth",
            headers=headers,
        )
        payload = _json_object(body, phase="api_auth")
        if payload.get("error", {}).get("category") != "authentication":
            raise ReleaseGateError("api_auth", f"{label} Bearer response is invalid.")
    _headers, body = _require_http(
        "GET",
        f"{base_url}/api/v1/analyses/unknown",
        expected_status=404,
        phase="api_auth",
        headers={"Authorization": bearer_header},
    )
    _json_object(body, phase="api_auth")
    return {
        "status": "passed",
        "missing_bearer_status": 401,
        "invalid_bearer_status": 401,
        "valid_bearer_reached_route_status": 404,
    }


def _verify_no_demo_copies_outside_demo(work: Path) -> bool:
    demo_root = (work / "demo-media").resolve()
    for path in work.rglob("*"):
        if path.is_file() and path.name in _DEMO_NAMES.values():
            resolved = path.resolve()
            if demo_root not in resolved.parents:
                return False
    return True


def _retrieve_after_restart(
    *,
    base_url: str,
    results: dict[str, dict[str, Any]],
    bearer_header: str,
) -> dict[str, Any]:
    retrieved: dict[str, Any] = {}
    for analysis_id, expected in results.items():
        _headers, body = _require_http(
            "GET",
            f"{base_url}/api/v1/analyses/{analysis_id}/result",
            expected_status=200,
            phase="restart_retrieval",
            headers={"Authorization": bearer_header},
        )
        actual = _json_object(body, phase="restart_retrieval")
        if actual != expected:
            raise ReleaseGateError(
                "restart_retrieval",
                "Restart result differs from the first process result.",
                analysis_id=analysis_id,
            )
        _status_headers, status_body = _require_http(
            "GET",
            f"{base_url}/api/v1/analyses/{analysis_id}",
            expected_status=200,
            phase="restart_retrieval",
            headers={"Authorization": bearer_header},
        )
        status_payload = _json_object(status_body, phase="restart_retrieval")
        if not status_payload.get("result_available"):
            raise ReleaseGateError(
                "restart_retrieval",
                "Restart status does not expose the persisted result.",
                analysis_id=analysis_id,
            )
        retrieved[analysis_id] = {
            "result_status": 200,
            "status_status": 200,
            "result_available": True,
            "semantic_match": True,
        }
    return retrieved


def _initial_report(*, output: Path, development: bool) -> dict[str, Any]:
    return {
        "tool_version": _TOOL_VERSION,
        "certification_mode": "development" if development else "strict",
        "certified": False,
        "source_sha": None,
        "source_sha_at_end": None,
        "source_sha_stable": None,
        "source_tree_clean": False,
        "package_version": None,
        "output_directory": str(output),
        "overall_status": "running",
    }


def _write_report(
    report: dict[str, Any],
    *,
    output: Path,
    secret_values: tuple[str, ...],
) -> None:
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    rendered = _redact(rendered, secret_values)
    (output / _REPORT_NAME).write_text(rendered, encoding="utf-8")


def run_release_gate(
    *,
    output_directory: Path | None = None,
    development: bool = False,
) -> dict[str, Any]:
    """Run the complete installed-artifact release gate and return its report."""
    repository = Path(__file__).resolve().parents[1]
    output = _prepare_output_directory(output_directory, repository)
    report = _initial_report(output=output, development=development)
    secret_values: tuple[str, ...] = ()
    active_server: _ServerProcess | None = None

    try:
        _announce("source preflight")
        env = _sanitized_environment()
        git = shutil.which("git", path=env.get("PATH"))
        uv = shutil.which("uv", path=env.get("PATH"))
        if git is None or uv is None:
            raise ReleaseGateError("source", "git and uv are required.")
        source_sha = _run_command(
            [git, "rev-parse", "HEAD"],
            cwd=repository,
            env=env,
            timeout=10.0,
            phase="source",
        ).stdout.strip()
        source_status = _run_command(
            [git, "status", "--short", "--untracked-files=all"],
            cwd=repository,
            env=env,
            timeout=10.0,
            phase="source",
        ).stdout.splitlines()
        report["source_sha"] = source_sha
        report["source_status_at_start"] = source_status
        certification = _certification_state(
            development=development,
            source_status=source_status,
        )
        report.update(certification)

        machine = platform.machine()
        if (
            sys.platform != "win32"
            or machine.casefold() not in {"amd64", "x86_64"}
            or sys.version_info[:2] != (3, 12)
        ):
            raise ReleaseGateError(
                "prerequisites",
                "Stage 10 certification requires Windows x64 and Python 3.12.",
            )
        report["host_platform"] = {
            "system": platform.system(),
            "release": platform.release(),
            "machine": machine,
            "python_version": platform.python_version(),
        }

        pyproject = tomllib.loads((repository / "pyproject.toml").read_text(encoding="utf-8"))
        project_name, project_version = _project_identity(pyproject)
        report["project_name"] = project_name
        report["package_version"] = project_version
        uv_version = _run_command(
            [uv, "--version"],
            cwd=output,
            env=env,
            timeout=10.0,
            phase="prerequisites",
        ).stdout.strip()
        ffmpeg_version = _probe_external_tool("ffmpeg", cwd=output, env=env)
        ffprobe_version = _probe_external_tool("ffprobe", cwd=output, env=env)
        report["ffmpeg"] = {"version": ffmpeg_version, "external_prerequisite": True}
        report["ffprobe"] = {"version": ffprobe_version, "external_prerequisite": True}

        _announce("build sdist, wheel, and runtime constraints")
        build_inputs = _build_release_inputs(
            repository=repository,
            output=output,
            project_name=project_name,
            uv=uv,
            env=env,
        )
        wheel = build_inputs["wheel"]
        constraints = build_inputs["constraints"]
        report["build"] = {
            "status": "passed",
            "method": "uv build --sdist, then uv build --wheel from the sdist",
            "sdist_filename": build_inputs["sdist"].name,
            "wheel_filename": wheel.name,
            "wheel_sha256": _sha256_file(wheel),
            "constraints_generation_command": build_inputs["constraints_command"],
            "constraints_sha256": _sha256_file(constraints),
            "uv_version": uv_version,
            "backend": pyproject["build-system"]["build-backend"],
            "backend_requirements": pyproject["build-system"]["requires"],
        }

        _announce("assemble release kit, manifest, and ZIP")
        verification_python_version = platform.python_version()
        kit, manifest, manifest_sha256, file_hashes = _assemble_release_kit(
            repository=repository,
            output=output,
            project_name=project_name,
            wheel=wheel,
            constraints=constraints,
            manifest_arguments={
                "product_name": project_name,
                "package_version": project_version,
                "source_head_sha": source_sha,
                "source_tree_clean_at_build_start": certification["source_tree_clean"],
                "certification_mode": certification["certification_mode"],
                "python_version": verification_python_version,
                "uv_version": uv_version,
                "build_backend": pyproject["build-system"]["build-backend"],
                "build_requirements": pyproject["build-system"]["requires"],
                "ffmpeg_version": ffmpeg_version,
                "ffprobe_version": ffprobe_version,
            },
        )
        expected_kit_names = _expected_kit_names(wheel.name)
        zip_path = output / f"{project_name}-{project_version}-windows-x64.zip"
        _create_zip(kit, zip_path, expected_kit_names)
        extraction, zip_verification = _verify_zip(
            zip_path=zip_path,
            output=output,
            expected_names=expected_kit_names,
            manifest=manifest,
            manifest_sha256=manifest_sha256,
        )
        report["release_kit"] = {
            "status": "passed",
            "directory_name": kit.name,
            "inventory": sorted(expected_kit_names),
            "covered_file_hashes": file_hashes,
            "manifest": _MANIFEST_NAME,
            "manifest_sha256": manifest_sha256,
            "manifest_self_hash_strategy": "reported outside manifest",
            "zip_filename": zip_path.name,
            "zip_sha256": _sha256_file(zip_path),
            "zip_verified": zip_verification,
        }

        _announce("create fresh venv and install ZIP wheel")
        python, cli, environment_evidence = _create_and_verify_venv(
            repository=repository,
            output=output,
            extraction=extraction,
            wheel_filename=wheel.name,
            uv=uv,
            env=env,
            project_name=project_name,
            project_version=project_version,
        )
        report["environment"] = {
            **environment_evidence,
            "fresh_venv_class": "external release-gate output outside repository",
            "pythonhome_sanitized": True,
            "pythonpath_sanitized": True,
            "virtual_env_sanitized": True,
            "cli_help": "passed",
        }

        _announce("run release-kit demo generator")
        work = output / "gate-work"
        work.mkdir()
        media, demo_evidence = _generate_demo_media(
            python=python,
            extraction=extraction,
            work=work,
            env=env,
        )
        report["demo"] = demo_evidence

        api_token = secrets.token_urlsafe(32)
        webui_username = f"gate-{secrets.token_hex(6)}"
        webui_password = secrets.token_urlsafe(24)
        basic_credentials, basic_header, bearer_header, secret_values = (
            _auth_headers_and_redaction_values(
                api_token=api_token,
                webui_username=webui_username,
                webui_password=webui_password,
            )
        )
        child_env = env.copy()
        child_env["MEDIA_ANALYZER_API_TOKEN"] = api_token
        child_env["MEDIA_ANALYZER_WEBUI_CREDENTIALS"] = basic_credentials
        initial_port = _reserve_loopback_port()
        config_path, config_raw = _prepare_work_config(
            extraction=extraction,
            work=work,
            port=initial_port,
            secret_values=secret_values,
        )
        report["work_config"] = {
            "status": "passed",
            "source": "verified ZIP config.example.yaml copy",
            "profile_b": _profile_b_ids(config_raw),
            "private_runtime_root": str((work / "runtime").resolve()),
            "secrets_in_config": False,
            "bounded_processing_seconds": 120,
            "bounded_analyzer_seconds": 60,
        }
        report["auth_secrets"] = {
            "status": "passed",
            "generation": "Python secrets module",
            "transport": "child process environment only",
            "persisted": False,
            "reported": False,
        }

        _announce("start installed CLI process 1 and exercise real HTTP")
        active_server, startup_1 = _start_server_with_bind_retry(
            cli=cli,
            config_path=config_path,
            config_raw=config_raw,
            work=work,
            env=child_env,
            secret_values=secret_values,
        )
        port = active_server.port
        base_url = f"http://127.0.0.1:{port}"
        startup_1["command_pattern"] = (
            f"<fresh-venv>\\Scripts\\{project_name}.exe "
            "--config <private-gate-work>\\config.yaml"
        )
        api_auth_evidence = _exercise_api_auth(base_url, bearer_header)

        all_results: dict[str, dict[str, Any]] = {}
        persistence_evidence: list[dict[str, Any]] = []
        web_result, web_analysis, web_persistence, webui_evidence = _exercise_webui(
            base_url=base_url,
            image_path=media[".png"],
            basic_header=basic_header,
            bearer_header=bearer_header,
            config_raw=config_raw,
            expected_application_version=project_version,
        )
        web_analysis_id = web_result["analysis_id"]
        all_results[web_analysis_id] = web_result
        persistence_evidence.append(web_persistence)

        api_evidence: dict[str, Any] = {}
        for media_name, suffix in (("image", ".png"), ("audio", ".wav"), ("video", ".mp4")):
            result, evidence, persistence = _submit_api_analysis(
                base_url=base_url,
                path=media[suffix],
                bearer_header=bearer_header,
                config_raw=config_raw,
                expected_application_version=project_version,
            )
            all_results[result["analysis_id"]] = result
            persistence_evidence.append(persistence)
            api_evidence[media_name] = evidence

        if not _verify_no_demo_copies_outside_demo(work):
            raise ReleaseGateError("cleanup", "Demo media escaped the gate-owned demo directory.")
        report["server_1"] = {
            "startup": startup_1,
            "health": startup_1["health"],
            "webui_auth_and_upload": webui_evidence,
            "webui_analysis": web_analysis,
            "api_auth": api_auth_evidence,
            "api_image": api_evidence["image"],
            "api_audio": api_evidence["audio"],
            "api_video": api_evidence["video"],
            "persistence": persistence_evidence,
            "cleanup": {
                "status": "passed",
                "analysis_count": len(persistence_evidence),
                "workspaces_absent": True,
                "quarantine_residue_absent": True,
                "demo_media_confined": True,
            },
        }

        _announce("gracefully stop installed CLI process 1")
        shutdown_1 = _graceful_shutdown(active_server, secret_values=secret_values)
        report["server_1"]["shutdown"] = shutdown_1
        active_server = None

        _announce("restart installed CLI and retrieve persisted results")
        active_server, startup_2 = _start_server_same_config(
            cli=cli,
            config_path=config_path,
            work=work,
            env=child_env,
            port=port,
            secret_values=secret_values,
        )
        restarted_url = f"http://127.0.0.1:{port}"
        restart_retrieval = _retrieve_after_restart(
            base_url=restarted_url,
            results=all_results,
            bearer_header=bearer_header,
        )
        _web_headers, web_restart_body = _require_http(
            "GET",
            f"{restarted_url}/analyses/{web_analysis_id}/result",
            expected_status=200,
            phase="webui_restart",
            headers={"Authorization": basic_header},
        )
        if web_analysis_id.encode("utf-8") not in web_restart_body:
            raise ReleaseGateError(
                "webui_restart",
                "Restarted WebUI did not render the prior result.",
                analysis_id=web_analysis_id,
            )
        report["server_2"] = {
            "startup": startup_2,
            "restart_retrieval": restart_retrieval,
            "webui_restart": {
                "status": "passed",
                "analysis_id": web_analysis_id,
                "http_status": 200,
            },
        }

        _announce("gracefully stop installed CLI process 2")
        shutdown_2 = _graceful_shutdown(active_server, secret_values=secret_values)
        report["server_2"]["shutdown"] = shutdown_2
        active_server = None
        report["process_cleanup"] = {
            "listener_closed": shutdown_1["listener_closed"] and shutdown_2["listener_closed"],
            "processes_reaped": shutdown_1["process_reaped"] and shutdown_2["process_reaped"],
            "owned_server_process_count": 2,
            "broad_system_cleanup_used": False,
        }

        _announce("final source and release-kit integrity checks")
        final_source_sha = _run_command(
            [git, "rev-parse", "HEAD"],
            cwd=repository,
            env=env,
            timeout=10.0,
            phase="source",
        ).stdout.strip()
        report["source_sha_at_end"] = final_source_sha
        report["source_sha_stable"] = final_source_sha == source_sha
        _require_stable_source_sha(initial_sha=source_sha, final_sha=final_source_sha)
        final_source_status = _run_command(
            [git, "status", "--short", "--untracked-files=all"],
            cwd=repository,
            env=env,
            timeout=10.0,
            phase="source",
        ).stdout.splitlines()
        report["source_status_at_end"] = final_source_status
        if not development and final_source_status:
            raise ReleaseGateError("source", "Source tree became dirty during strict gate.")
        if final_source_status != source_status:
            raise ReleaseGateError("source", "Release gate changed repository status.")
        for name, expected_hash in file_hashes.items():
            if _sha256_file(kit / name) != expected_hash:
                raise ReleaseGateError("release_kit", f"Release-kit input changed: {name}.")
        if _sha256_file(kit / _MANIFEST_NAME) != manifest_sha256:
            raise ReleaseGateError("release_kit", "Release manifest changed after assembly.")

        report["certified"] = bool(not development and not final_source_status)
        report["source_tree_clean"] = not final_source_status
        report["overall_status"] = "development_pass" if development else "passed"
        _write_report(report, output=output, secret_values=secret_values)
        return report
    except BaseException as caught:
        # Reap the owned server even when the operator interrupts the gate.
        error = (
            caught
            if isinstance(caught, ReleaseGateError)
            else ReleaseGateError(
                "internal",
                f"Unexpected release-gate failure: {type(caught).__name__}.",
            )
        )
        if active_server is not None:
            emergency_tail = active_server.output_tail(secret_values)
            _emergency_stop(active_server)
            if error.server_output_tail is None:
                error.server_output_tail = emergency_tail
        report["certified"] = False
        report["overall_status"] = "failed"
        report["failure"] = {
            "phase": error.phase,
            "message": _redact(str(error), secret_values),
            "analysis_id": error.analysis_id,
            "process_returncode": error.process_returncode,
            "server_output_tail": _redact(error.server_output_tail or "", secret_values),
        }
        _write_report(report, output=output, secret_values=secret_values)
        if not isinstance(caught, Exception):
            raise
        return report


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assemble and exercise the complete Stage 10 release handoff."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="empty directory outside the repository; defaults to an OS temp directory",
    )
    parser.add_argument(
        "--development",
        action="store_true",
        help="allow a dirty source tree but produce non-certifying evidence",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        report = run_release_gate(
            output_directory=args.output_dir,
            development=args.development,
        )
    except ReleaseGateError as error:
        print(f"Stage 10 release verification failed in {error.phase}: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["overall_status"] in {"passed", "development_pass"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
