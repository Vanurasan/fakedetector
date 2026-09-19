"""Source certification, supported host prerequisites and locked artifact builds."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import verify_release_package as package_verifier

from . import common

_WINDOWS_11_MIN_BUILD = 22000


_WINDOWS_NT_WORKSTATION = 1


def _certification_state(*, development: bool, source_status: list[str]) -> dict[str, Any]:
    source_tree_clean = not source_status
    if not development and not source_tree_clean:
        raise common.ReleaseVerificationError(
            "source",
            "Strict certification requires a clean tracked and untracked source tree.",
        )
    return {
        "certification_mode": "development" if development else "strict",
        "source_tree_clean": source_tree_clean,
        "certified": bool(not development and source_tree_clean),
    }


def _validate_supported_host(
    *,
    platform_name: str,
    machine: str,
    python_version: tuple[int, int],
    windows_major: int | None,
    windows_build: int | None,
    windows_product_type: int | None,
) -> None:
    if (
        platform_name != "win32"
        or machine.casefold() not in {"amd64", "x86_64"}
        or python_version != (3, 12)
        or windows_major != 10
        or windows_build is None
        or windows_build < _WINDOWS_11_MIN_BUILD
        or windows_product_type != _WINDOWS_NT_WORKSTATION
    ):
        raise common.ReleaseVerificationError(
            "prerequisites",
            "release certification requires Windows 11 x64 workstation "
            "(build 22000 or newer) and Python 3.12.",
        )


def _project_identity(pyproject: dict[str, Any]) -> tuple[str, str]:
    project = pyproject.get("project")
    if not isinstance(project, dict):
        raise common.ReleaseVerificationError("source", "pyproject.toml lacks [project] metadata.")
    name = project.get("name")
    version = project.get("version")
    if not isinstance(name, str) or not name or not isinstance(version, str) or not version:
        raise common.ReleaseVerificationError(
            "source", "pyproject.toml project name/version is invalid."
        )
    return name, version


def _require_stable_source_sha(*, initial_sha: str, final_sha: str) -> None:
    if final_sha != initial_sha:
        raise common.ReleaseVerificationError("source", "HEAD changed during the release gate.")


def _probe_external_tool(
    executable_name: str,
    *,
    cwd: Path,
    env: dict[str, str],
) -> str:
    executable = shutil.which(executable_name, path=env.get("PATH"))
    if executable is None:
        raise common.ReleaseVerificationError(
            "prerequisites", f"{executable_name} is not available on PATH."
        )
    completed = common._run_command(
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
        raise common.ReleaseVerificationError(
            "prerequisites", f"{executable_name} returned no version evidence."
        )
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
    common._run_command(
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
        timeout=common._PHASE_TIMEOUTS["build"],
        phase="build_sdist",
    )
    try:
        sdist = package_verifier._single_artifact(artifacts, f"{project_name}-*.tar.gz")
    except package_verifier.VerificationError as error:
        raise common.ReleaseVerificationError("build_sdist", str(error)) from None
    common._run_command(
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
        timeout=common._PHASE_TIMEOUTS["build"],
        phase="build_wheel",
    )
    try:
        wheel = package_verifier._single_artifact(artifacts, f"{project_name}-*.whl")
    except package_verifier.VerificationError as error:
        raise common.ReleaseVerificationError("build_wheel", str(error)) from None

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
    common._run_command(
        constraints_command,
        cwd=repository,
        env=env,
        timeout=common._PHASE_TIMEOUTS["constraints"],
        phase="constraints",
    )
    return {
        "sdist": sdist,
        "wheel": wheel,
        "constraints": constraints,
        "constraints_command": subprocess.list2cmdline(constraints_command),
    }
