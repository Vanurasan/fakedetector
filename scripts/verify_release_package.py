"""Build and verify product release artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import tomllib
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

_PROJECT_NAME = "fakedetector"
_REQUIRED_RESOURCES = (
    "templates/error.html",
    "templates/result.html",
    "templates/status.html",
    "templates/upload.html",
    "static/styles.css",
)
_IGNORED_VENV_TOOLING = frozenset({"pip", "setuptools", "wheel"})


class VerificationError(RuntimeError):
    """Raised when an installed artifact does not satisfy the release checks."""


def _run(
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
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
        )
    except subprocess.CalledProcessError as error:
        command = subprocess.list2cmdline(args)
        raise VerificationError(
            f"Command failed: {command}\nstdout:\n{error.stdout}\nstderr:\n{error.stderr}"
        ) from error


def _single_artifact(directory: Path, pattern: str) -> Path:
    matches = sorted(directory.glob(pattern))
    if len(matches) != 1:
        raise VerificationError(
            f"Expected exactly one artifact matching {pattern!r}, found {len(matches)}."
        )
    return matches[0].resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_sdist_provenance(sdist: Path, *, repository: Path) -> None:
    """Accept only tracked working-tree files and Hatchling's root PKG-INFO.

    Use working-tree bytes so development verification supports tracked edits.
    Strict certification separately requires a clean tree at a stable Git SHA.
    """
    tracked = set(
        _run(["git", "ls-files", "-z"], cwd=repository).stdout.rstrip("\0").split("\0")
    )
    if not tracked or "" in tracked:
        raise VerificationError("Sdist provenance requires tracked repository source files.")
    expected = tracked | {"PKG-INFO"}
    seen: set[str] = set()
    root = sdist.name.removesuffix(".tar.gz")
    with tarfile.open(sdist, "r:gz") as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if (
                not member.isfile()
                or len(path.parts) < 2
                or path.parts[0] != root
                or ".." in path.parts
                or "\\" in member.name
                or path.as_posix() != member.name
            ):
                raise VerificationError(f"Invalid sdist source member: {member.name!r}")
            relative = PurePosixPath(*path.parts[1:]).as_posix()
            if relative not in expected or relative in seen:
                raise VerificationError(f"Untracked or duplicate sdist source member: {relative!r}")
            seen.add(relative)
            if relative == "PKG-INFO":
                continue
            source = repository / relative
            if not source.resolve().is_relative_to(repository.resolve()) or not source.is_file():
                raise VerificationError(f"Sdist source is outside the repository: {relative!r}")
            stream = archive.extractfile(member)
            assert stream is not None
            with stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest != _sha256(source):
                raise VerificationError(f"Sdist source differs from working tree: {relative!r}")
    if seen != expected:
        raise VerificationError(f"Sdist source inventory is incomplete: {sorted(expected - seen)}")


def _sanitized_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
        environment.pop(name, None)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PIP_CONFIG_FILE"] = os.devnull
    return environment


def _parse_constraints(
    path: Path,
    marker_environment: dict[str, str],
) -> dict[str, str]:
    expected: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        requirement = Requirement(line)
        if requirement.marker is not None and not requirement.marker.evaluate(
            environment=marker_environment
        ):
            continue
        exact_versions = [
            specifier.version
            for specifier in requirement.specifier
            if specifier.operator == "==" and not specifier.version.endswith(".*")
        ]
        if len(exact_versions) != 1 or len(requirement.specifier) != 1:
            raise VerificationError(f"Constraint is not one exact pin: {line}")
        name = canonicalize_name(requirement.name)
        previous = expected.setdefault(name, exact_versions[0])
        if previous != exact_versions[0]:
            raise VerificationError(f"Conflicting applicable constraints for {name}.")
    return expected


def _direct_dev_names(pyproject_path: Path) -> set[str]:
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    requirements = pyproject.get("dependency-groups", {}).get("dev", [])
    return {canonicalize_name(Requirement(item).name) for item in requirements}


def _assert_runtime_matches_constraints(
    *,
    installed: dict[str, str],
    expected: dict[str, str],
    direct_dev_names: set[str],
) -> dict[str, Any]:
    project_name = canonicalize_name(_PROJECT_NAME)
    normalized_installed = {canonicalize_name(name): version for name, version in installed.items()}
    runtime_installed = {
        name: version
        for name, version in normalized_installed.items()
        if name != project_name and name not in _IGNORED_VENV_TOOLING
    }
    missing = sorted(name for name in expected if name not in runtime_installed)
    unexpected = sorted(name for name in runtime_installed if name not in expected)
    mismatched = {
        name: {"expected": expected[name], "installed": runtime_installed[name]}
        for name in sorted(expected.keys() & runtime_installed.keys())
        if expected[name] != runtime_installed[name]
    }
    dev_only_installed = sorted(
        name for name in direct_dev_names if name in runtime_installed and name not in expected
    )
    if missing or unexpected or mismatched or dev_only_installed:
        raise VerificationError(
            "Runtime dependency comparison failed: "
            + json.dumps(
                {
                    "missing": missing,
                    "unexpected": unexpected,
                    "mismatched": mismatched,
                    "dev_only_installed": dev_only_installed,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    return {
        "status": "match",
        "approved_distribution_count": len(expected),
        "installed_runtime_distribution_count": len(runtime_installed),
        "dev_only_installed": dev_only_installed,
    }


def _installed_probe(python: Path, *, cwd: Path, env: dict[str, str]) -> dict[str, Any]:
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
        from fakedetector.app import create_app
        from fakedetector.config.models import AppConfig, ServerConfig

        distribution = metadata.distribution("{_PROJECT_NAME}")
        direct_url_text = distribution.read_text("direct_url.json")
        direct_url = json.loads(direct_url_text) if direct_url_text else None
        resource_root = resources.files("fakedetector")
        resource_paths = {{
            name: str(resource_root.joinpath(name))
            for name in {list(_REQUIRED_RESOURCES)!r}
            if resource_root.joinpath(name).is_file()
        }}
        installed = {{
            item.metadata["Name"]: item.version
            for item in metadata.distributions()
            if item.metadata["Name"]
        }}
        implementation = sys.implementation.version
        implementation_version = ".".join(
            str(part)
            for part in (implementation.major, implementation.minor, implementation.micro)
        )
        marker_environment = {{
            "implementation_name": sys.implementation.name,
            "implementation_version": implementation_version,
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
        config = AppConfig.model_validate({{
            "schema_version": "1.0",
            "server": {{}},
            "access_channels": {{
                "webui": {{"enabled": False}},
                "api": {{"enabled": False}},
            }},
            "limits": {{}},
            "allowed_formats": {{}},
            "validation": {{}},
            "temporary_storage": {{}},
            "preprocessing": {{}},
            "analyzers": {{}},
            "risk_assessment": {{}},
            "result": {{}},
            "error_handling": {{}},
            "logging": {{}},
            "external_systems": {{}},
        }})
        import hashlib
        import io
        import jpegio
        from PIL import Image
        from fakedetector._generated_artifact_budget import _GeneratedArtifactBudget
        from fakedetector.config._snapshot import _ConfigSnapshot
        from fakedetector.domain import MediaType, ImageTechnicalParameters, ValidatedFileDescriptor
        from fakedetector.intake.temporary_input import LocalTemporaryInputOwner, PreparedSourceRef
        from fakedetector.lifecycle.artifacts import WorkspaceArtifactRegistry
        from fakedetector.preprocessing._errors import PreprocessingError
        from fakedetector.preprocessing._requirements import (
            ForensicCapability, PreprocessingRequirements,
        )
        from fakedetector.preprocessing._service import (
            PreprocessingDispatcher, PreprocessingRequest,
        )

        assert metadata.version("pyjpegio") == "0.3.0"
        jpeg_origin = Path(jpegio.__file__).resolve()
        assert jpeg_origin.is_relative_to(Path(sys.prefix))
        buffer = io.BytesIO()
        with Image.new("RGB", (17, 17), (40, 80, 120)) as image:
            image.save(buffer, "JPEG", progressive=True)
        jpeg = buffer.getvalue()
        oversized = bytearray(jpeg)
        sof = oversized.index(b"\\xff\\xc2")
        oversized[sof + 5:sof + 9] = b"\\xff" * 4
        jpeg_root = Path.cwd() / "jpeg-\u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0430"
        jpeg_results = []
        for index, (payload, expected) in enumerate(((jpeg, "clean"), (jpeg[:-2], "decode"),
                                                     (bytes(oversized), "resource_limit"))):
            owner = LocalTemporaryInputOwner(jpeg_root)
            analysis_id = format(index + 1, "032x")
            owned = owner.create(analysis_id)
            owner.ingest(owned, io.BytesIO(payload), len(payload) + 1)
            accepted = owner.transfer(owned)
            registry = WorkspaceArtifactRegistry(jpeg_root / analysis_id)
            descriptor = ValidatedFileDescriptor(
                original_name="image.jpg", extension="jpg", declared_mime_type=None,
                detected_mime_type="image/jpeg", media_type=MediaType.IMAGE,
                size_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest(),
                signature_match=True, safe_read=True,
                technical_parameters=ImageTechnicalParameters(width=17, height=17,
                    format="JPEG", color_mode="RGB", frame_count=1, has_metadata=False),
            )
            try:
                prepared = PreprocessingDispatcher(config).prepare(
                    PreprocessingRequest(analysis_id=analysis_id, validated_file=descriptor,
                        source_file_ref=PreparedSourceRef(accepted), artifact_registry=registry,
                        artifact_budget=_GeneratedArtifactBudget(
                            _ConfigSnapshot.capture(config), MediaType.IMAGE)),
                    PreprocessingRequirements(forensic=frozenset({{ForensicCapability.JPEG_COEFFICIENTS}})),
                )
                assert expected == "clean" and len(prepared.artifacts) == 4
                assert prepared.forensic.source_sha256 == descriptor.sha256
                planes = prepared.forensic.representations[1].facts.planes
                for plane, artifact in zip(planes, prepared.artifacts[1:], strict=True):
                    length = registry.with_local_artifact_path(
                        artifact.artifact_ref, lambda p: p.stat().st_size)
                    assert length == plane.nbytes
                jpeg_results.append("clean")
            except PreprocessingError as error:
                assert error.kind == expected
                jpeg_results.append(error.kind)
            finally:
                assert registry.cleanup_once().completed
                accepted.cleanup()
                assert not (jpeg_root / analysis_id).exists()
        jpeg_root.rmdir()
        import subprocess
        import wave
        import numpy as np
        from fakedetector.preprocessing import _media_tools as mt
        from fakedetector.preprocessing._models import IndexRange, AVTimelineDescriptor
        audio_path = Path.cwd() / "macro1.wav"
        video_path = Path.cwd() / "macro1.mp4"
        pixel_path = Path.cwd() / "macro1.rgb"
        with wave.open(str(audio_path), "wb") as stream:
            stream.setparams((1, 4, 8000, 0, "NONE", "none"))
            stream.writeframes(np.arange(8000, dtype="<i4").tobytes())
        tool = mt._FFmpegPreprocessingTool(executable="ffmpeg", timeout_seconds=30)
        precision = tool.audio_precision(audio_path, timeout_seconds=30)
        samples = tool.precision_window(audio_path, precision, IndexRange(start=0, stop=8000),
                                        timeout_seconds=30)
        assert np.array_equal(samples.values[:, 0], np.arange(8000))
        spectra = list(mt.stft_batches(samples.values, sample_rate=8000, n_fft=4096, hop=1024))
        assert spectra and not spectra[0].values.flags.writeable
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-f", "lavfi", "-i",
                        "testsrc2=size=64x48:rate=25:duration=1", "-i", str(audio_path),
                        "-c:v", "mpeg4", "-c:a", "aac", str(video_path)],
                       check=True, capture_output=True, timeout=30)
        video = tool.timing_stream(video_path, kind="video", frames=True, timeout_seconds=30)
        audio = tool.timing_stream(video_path, kind="audio", frames=False, timeout_seconds=30)
        interval = mt.select_timing_regions(video)[0]
        generic, gv = tool.timing_records(
            video_path, video, interval, 0, "frame", timeout_seconds=30)
        packets, pv = tool.timing_records(video_path, audio, mt.select_timing_regions(audio)[0],
                                          0, "packet", timeout_seconds=30)
        dense, timing, tv = tool.dense_window(video_path, pixel_path, video, interval, 0,
            artifact_budget=_GeneratedArtifactBudget(
                _ConfigSnapshot.capture(config), MediaType.VIDEO),
            timeout_seconds=30)
        assert dense.decode_operation_id == timing.decode_operation_id
        assert generic.purpose == "generic" and timing.purpose == "dense"
        assert generic.data.artifact_id != timing.data.artifact_id
        assert pixel_path.stat().st_size == dense.pixels.nbytes
        assert len(gv) == len(tv) == 25
        mapping = AVTimelineDescriptor.from_timing((video, audio), (generic, packets, timing))
        assert mapping.applicability == "available" and len(mapping.regions) == 1
        macro1_probe = {{"audio_precision_stft": "passed", "generic_timing": "passed",
                        "dense_same_decode": "passed", "av_mapping": "passed"}}
        for path in (audio_path, video_path, pixel_path):
            path.unlink()
        app = create_app(config)
        print(json.dumps({{
            "package_version": distribution.version,
            "module_version": fakedetector.__version__,
            "config_default_application_version": ServerConfig().application_version,
            "fastapi_version": app.version,
            "module_origin": str(Path(fakedetector.__file__).resolve()),
            "create_app_module": create_app.__module__,
            "direct_url": direct_url,
            "resources": resource_paths,
            "installed": installed,
            "marker_environment": marker_environment,
            "python_version": platform.python_version(),
            "sys_path": sys.path,
            "user_site_enabled": bool(__import__("site").ENABLE_USER_SITE),
            "macro1_probe": macro1_probe,
            "jpeg_probe": {{"version": metadata.version("pyjpegio"), "origin": str(jpeg_origin),
                            "outcomes": jpeg_results, "unicode_workspace": True,
                            "cleanup": "passed"}},
        }}, sort_keys=True))
        """
    )
    completed = _run([str(python), "-I", "-c", probe], cwd=cwd, env=env)
    return json.loads(completed.stdout)


def _prepare_output_directory(requested: Path | None) -> Path:
    if requested is None:
        return Path(tempfile.mkdtemp(prefix="fakedetector-release-")).resolve()
    output = requested.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise VerificationError("The verification output directory must be empty.")
    return output


def verify(output_directory: Path | None = None) -> dict[str, Any]:
    """Build from sdist, install the exact wheel, and return verification evidence."""
    repository = Path(__file__).resolve().parents[1]
    output = _prepare_output_directory(output_directory)
    if output == repository or repository in output.parents:
        raise VerificationError("Verification output must be outside the repository.")

    uv = shutil.which("uv")
    if uv is None:
        raise VerificationError("uv is required for release package verification.")

    artifacts = output / "artifacts"
    artifacts.mkdir()
    constraints = output / "runtime-constraints.txt"
    environment = _sanitized_environment()

    source_sha = _run(["git", "rev-parse", "HEAD"], cwd=repository, env=environment).stdout.strip()
    source_status = _run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=repository,
        env=environment,
    ).stdout.splitlines()
    uv_version = _run([uv, "--version"], cwd=output, env=environment).stdout.strip()
    pyproject = tomllib.loads((repository / "pyproject.toml").read_text(encoding="utf-8"))
    project_version = pyproject["project"]["version"]

    _run(
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
        env=environment,
    )
    sdist = _single_artifact(artifacts, f"{_PROJECT_NAME}-*.tar.gz")
    _verify_sdist_provenance(sdist, repository=repository)
    _run(
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
        env=environment,
    )
    wheel = _single_artifact(artifacts, f"{_PROJECT_NAME}-*.whl")
    expected_wheel_resources = {f"fakedetector/{resource}" for resource in _REQUIRED_RESOURCES}
    with zipfile.ZipFile(wheel) as archive:
        wheel_names = set(archive.namelist())
    missing_wheel_resources = sorted(expected_wheel_resources - wheel_names)
    if missing_wheel_resources:
        raise VerificationError(f"Wheel resources are missing: {missing_wheel_resources}")

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
    _run(constraints_command, cwd=repository, env=environment)

    venv = output / "venv"
    _run(
        [uv, "venv", "--python", "3.12", "--no-project", str(venv)],
        cwd=output,
        env=environment,
    )
    scripts_directory = venv / ("Scripts" if os.name == "nt" else "bin")
    python = scripts_directory / ("python.exe" if os.name == "nt" else "python")
    cli = scripts_directory / ("fakedetector.exe" if os.name == "nt" else "fakedetector")
    _run(
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
        env=environment,
    )
    _run(
        [uv, "pip", "check", "--python", str(python)],
        cwd=output,
        env=environment,
    )
    probe = _installed_probe(python, cwd=output, env=environment)

    if probe["package_version"] != project_version:
        raise VerificationError("Installed distribution version differs from build metadata.")
    if probe["module_version"] != probe["package_version"]:
        raise VerificationError("fakedetector.__version__ differs from package metadata.")
    if probe["config_default_application_version"] != probe["package_version"]:
        raise VerificationError("Default application provenance differs from package metadata.")
    if probe["fastapi_version"] != probe["package_version"]:
        raise VerificationError("FastAPI metadata differs from package metadata.")
    if probe["create_app_module"] != "fakedetector.app":
        raise VerificationError("create_app was not imported from the installed package.")
    if probe["user_site_enabled"]:
        raise VerificationError("The isolated probe unexpectedly enabled user-site packages.")

    module_origin = Path(probe["module_origin"])
    if venv.resolve() not in module_origin.parents or "site-packages" not in {
        part.casefold() for part in module_origin.parts
    }:
        raise VerificationError("Imported module does not originate from venv site-packages.")
    if repository in module_origin.parents:
        raise VerificationError("Imported module leaked from the source checkout.")
    checkout_on_sys_path = False
    for raw_path in probe["sys_path"]:
        if not raw_path:
            continue
        candidate = Path(raw_path).resolve()
        if candidate == repository or repository in candidate.parents:
            checkout_on_sys_path = True
            break
    if checkout_on_sys_path:
        raise VerificationError("The source checkout leaked into isolated sys.path.")

    direct_url = probe["direct_url"]
    if not isinstance(direct_url, dict) or direct_url.get("url") != wheel.as_uri():
        raise VerificationError("Installed project does not identify the exact built wheel.")
    if direct_url.get("dir_info", {}).get("editable", False):
        raise VerificationError("Editable installation is not allowed.")

    missing_resources = sorted(set(_REQUIRED_RESOURCES) - probe["resources"].keys())
    if missing_resources:
        raise VerificationError(f"Installed resources are missing: {missing_resources}")
    expected = _parse_constraints(constraints, probe["marker_environment"])
    comparison = _assert_runtime_matches_constraints(
        installed=probe["installed"],
        expected=expected,
        direct_dev_names=_direct_dev_names(repository / "pyproject.toml"),
    )

    cli_result = _run([str(cli), "--help"], cwd=output, env=environment)
    if "usage:" not in cli_result.stdout.casefold():
        raise VerificationError("Installed CLI help did not return argparse usage.")

    report: dict[str, Any] = {
        "source_sha": source_sha,
        "source_tree_clean": not source_status,
        "package_version": probe["package_version"],
        "build_method": "uv build --sdist, then uv build --wheel from the sdist",
        "build_tooling": {
            "uv": uv_version,
            "backend": pyproject["build-system"]["build-backend"],
            "requires": pyproject["build-system"]["requires"],
        },
        "sdist_filename": sdist.name,
        "wheel_filename": wheel.name,
        "wheel_sha256": _sha256(wheel),
        "constraints_generation_command": subprocess.list2cmdline(constraints_command),
        "constraints_file": str(constraints),
        "fresh_venv_class": "temporary directory outside repository",
        "python_version": probe["python_version"],
        "installed_project_origin": probe["module_origin"],
        "installed_from_exact_wheel": True,
        "editable_install": False,
        "dependency_check": "passed",
        "jpeg_preprocessing": probe["jpeg_probe"],
        "macro1_preprocessing": probe["macro1_probe"],
        "runtime_dependency_comparison": comparison,
        "cli_help": "passed",
        "source_checkout_on_sys_path": False,
        "pythonpath_sanitized": True,
        "user_site_enabled": False,
        "wheel_resource_inventory": sorted(expected_wheel_resources),
        "installed_resource_inventory": sorted(probe["resources"]),
        "output_directory": str(output),
    }
    (output / "verification-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and verify the release wheel in an isolated venv."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="empty directory outside the repository; defaults to a new OS temp directory",
    )
    return parser.parse_args()


def main() -> int:
    """Run the release verification and emit its machine-readable report."""
    args = _parse_args()
    try:
        report = verify(args.output_dir)
    except VerificationError as error:
        print(f"release package verification failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
