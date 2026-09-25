"""release package-version and artifact regression tests."""

from __future__ import annotations

import configparser
import importlib.metadata
import subprocess
import sys
import tarfile
import textwrap
import tomllib
import zipfile
from email.parser import BytesParser
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml
from packaging.markers import Marker
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

import fakedetector
from fakedetector.app import create_app
from fakedetector.config.models import AppConfig, ServerConfig

_ROOT = Path(__file__).resolve().parents[1]
_RESOURCES = {
    "fakedetector/static/styles.css",
    "fakedetector/templates/error.html",
    "fakedetector/templates/result.html",
    "fakedetector/templates/status.html",
    "fakedetector/templates/upload.html",
}


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def _project_identity() -> tuple[str, str]:
    project = _load_toml(_ROOT / "pyproject.toml")["project"]
    return project["name"], project["version"]


def _requirements(path: Path) -> list[Requirement]:
    return [
        Requirement(line)
        for raw_line in path.read_text(encoding="utf-8").splitlines()
        if (line := raw_line.strip()) and not line.startswith("#")
    ]


def _locked_markers(value: object) -> set[str]:
    if isinstance(value, dict):
        markers = {
            str(Marker(marker)) for marker in [value.get("marker")] if isinstance(marker, str)
        }
        for child in value.values():
            markers.update(_locked_markers(child))
        return markers
    if isinstance(value, list):
        markers: set[str] = set()
        for child in value:
            markers.update(_locked_markers(child))
        return markers
    return set()


def _run(*args: str, cwd: Path = _ROOT) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def _config_with_disabled_channels() -> AppConfig:
    raw = yaml.safe_load((_ROOT / "config" / "config.example.yaml").read_text("utf-8"))
    raw["access_channels"]["api"]["enabled"] = False
    raw["access_channels"]["webui"]["enabled"] = False
    return AppConfig.model_validate(raw)


def test_package_metadata_is_the_runtime_version_source() -> None:
    project_name, expected_version = _project_identity()
    config = _config_with_disabled_channels()

    app = create_app(config)

    assert importlib.metadata.version(project_name) == expected_version
    assert fakedetector.__version__ == expected_version
    assert ServerConfig().application_version == expected_version
    assert config.server.application_version == expected_version
    assert app.version == expected_version


def test_application_version_explicit_override_remains_valid() -> None:
    config = ServerConfig(application_version="deployment-build-override")

    assert config.application_version == "deployment-build-override"
    assert config.model_dump()["application_version"] == "deployment-build-override"


def test_sdist_wheel_metadata_entry_point_and_resources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.syspath_prepend(str(_ROOT / "scripts"))
    import verify_release_package as verifier

    project_name, expected_version = _project_identity()
    artifact_name = project_name.replace("-", "_")
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    _run(
        "uv",
        "build",
        "--sdist",
        "--no-create-gitignore",
        "--out-dir",
        str(artifacts),
        str(_ROOT),
        cwd=tmp_path,
    )
    [sdist] = artifacts.glob(f"{artifact_name}-*.tar.gz")
    license_bytes = (_ROOT / "LICENSE").read_bytes()
    with tarfile.open(sdist, "r:gz") as archive:
        license_stream = archive.extractfile(f"{artifact_name}-{expected_version}/LICENSE")
        assert license_stream is not None
        with license_stream:
            assert license_stream.read() == license_bytes
    verifier._verify_sdist_provenance(sdist, repository=_ROOT)
    _run(
        "uv",
        "build",
        "--wheel",
        "--no-create-gitignore",
        "--out-dir",
        str(artifacts),
        str(sdist),
        cwd=tmp_path,
    )
    [wheel] = artifacts.glob(f"{artifact_name}-*.whl")

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        assert not any(name.startswith(("tests/", "support/")) for name in names)
        assert {
            "fakedetector/analyzers/_image_metadata.py",
            "fakedetector/analyzers/_image_copy_move.py",
            "fakedetector/analyzers/_image_jpeg_dq.py",
            "fakedetector/analyzers/_audio_pcm.py",
            "fakedetector/analyzers/_video_frames.py",
        } <= names
        for name in names:
            if name.endswith(".py"):
                source = archive.read(name)
                assert b"_FakeAnalyzer" not in source
                assert b"framework_test" not in source
                assert b"framework_analyzers" not in source
        metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
        entry_points_name = next(
            name for name in names if name.endswith(".dist-info/entry_points.txt")
        )
        metadata = BytesParser().parsebytes(archive.read(metadata_name))
        assert archive.read(
            f"{artifact_name}-{expected_version}.dist-info/licenses/LICENSE"
        ) == license_bytes
        entry_points = configparser.ConfigParser()
        entry_points.read_string(archive.read(entry_points_name).decode("utf-8"))

    assert sdist.name == f"{artifact_name}-{expected_version}.tar.gz"
    assert wheel.name == f"{artifact_name}-{expected_version}-py3-none-any.whl"
    assert metadata["Name"] == project_name
    assert metadata["Version"] == expected_version
    assert metadata["License-Expression"] == "Apache-2.0"
    assert metadata.get_all("License-File") == ["LICENSE"]
    assert entry_points["console_scripts"]["fakedetector"] == "fakedetector.main:main"
    assert names >= _RESOURCES

    installed = tmp_path / "installed"
    _run("uv", "pip", "install", "--no-deps", "--target", str(installed), str(wheel), cwd=tmp_path)
    probe = textwrap.dedent("""\
        import sys
        from pathlib import Path
        sys.path.insert(0, sys.argv[1])
        import fakedetector
        from fakedetector.analyzers._catalog import (
            _built_in_analyzer_registrations, _resolve_worker_definition,
        )
        from fakedetector.analyzers import _image_jpeg_dq
        from fakedetector.app import create_app
        from fakedetector.config.models import AppConfig
        assert Path(fakedetector.__file__).is_relative_to(Path(sys.argv[1]))
        assert sorted(
            (item.analyzer_id, item.analyzer_version)
            for item in _built_in_analyzer_registrations()
        ) == [
            ("audio_pcm_quality", "1.0.0"),
            ("image_copy_move_correspondence", "1.0.0"),
            ("image_jpeg_double_quantization", "1.0.0"),
            ("image_metadata_consistency", "1.0.0"),
            ("video_sampled_frame_quality", "1.0.0"),
        ]
        assert Path(_image_jpeg_dq.__file__).is_relative_to(Path(sys.argv[1]))
        dq = _resolve_worker_definition("stage12.image_jpeg_double_quantization.v1")
        assert dq is not None
        assert dq.factory is _image_jpeg_dq.ImageJpegDoubleQuantizationAnalyzer
        assert _resolve_worker_definition("framework_test.image") is None
        config = AppConfig.model_validate_json(Path(sys.argv[2]).read_bytes())
        app = create_app(config)
        assert app.state.runtime.application_service is app.state.application_service
        assert not config.external_systems.enabled
        """)
    config_path = tmp_path / "config.json"
    config_path.write_text(_config_with_disabled_channels().model_dump_json(), encoding="utf-8")
    _run(sys.executable, "-I", "-c", probe, str(installed), str(config_path), cwd=tmp_path)


@pytest.fixture
def source_inventory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.syspath_prepend(str(_ROOT / "scripts"))
    import verify_release_package as verifier

    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "README.md").write_bytes(b"tracked working-tree content\n")
    monkeypatch.setattr(
        verifier, "_run", lambda *a, **kw: SimpleNamespace(stdout="README.md\0"),
    )
    sdist = tmp_path / "fakedetector-0.1.0.tar.gz"

    def write(entries):
        with tarfile.open(sdist, "w:gz") as archive:
            for name, data, kind in entries:
                member = tarfile.TarInfo(f"fakedetector-0.1.0/{name}")
                member.type = kind
                member.size = len(data)
                archive.addfile(member, BytesIO(data))
        return sdist

    entries = [
        ("README.md", (repository / "README.md").read_bytes(), tarfile.REGTYPE),
        ("PKG-INFO", b"Metadata-Version: 2.4\n", tarfile.REGTYPE),
    ]
    return verifier, repository, write, entries


def test_sdist_accepts_tracked_working_bytes_and_generated_metadata(source_inventory) -> None:
    verifier, repository, write, entries = source_inventory
    verifier._verify_sdist_provenance(write(entries), repository=repository)


@pytest.mark.parametrize(
    "extra",
    ["graphify-out/graph.json", "local-tool/cache.dat", "src/local-tool/cache.dat",
     "tests/generated/local.py", "docs/local-notes.md", "nested/PKG-INFO"],
)
def test_sdist_rejects_generated_or_untracked_source(source_inventory, extra: str) -> None:
    verifier, repository, write, entries = source_inventory
    # The file really exists locally, but has no tracked provenance.
    local = repository / extra
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_bytes(b"local generated data")
    entries.append((extra, local.read_bytes(), tarfile.REGTYPE))
    with pytest.raises(verifier.VerificationError, match="Untracked"):
        verifier._verify_sdist_provenance(write(entries), repository=repository)


@pytest.mark.parametrize("defect", ["missing", "modified", "duplicate", "traversal", "symlink"])
def test_sdist_rejects_invalid_tracked_inventory(source_inventory, defect: str) -> None:
    verifier, repository, write, entries = source_inventory
    if defect == "missing":
        entries.pop(0)
    elif defect == "modified":
        entries[0] = ("README.md", b"wrong bytes", tarfile.REGTYPE)
    elif defect == "duplicate":
        entries.append(entries[0])
    elif defect == "traversal":
        entries[0] = ("../README.md", entries[0][1], tarfile.REGTYPE)
    else:
        entries[0] = ("README.md", b"", tarfile.SYMTYPE)
    with pytest.raises(verifier.VerificationError):
        verifier._verify_sdist_provenance(write(entries), repository=repository)


@pytest.mark.parametrize("entry_point", ["standalone", "full_release"])
def test_both_verifiers_reject_untracked_sdist_before_wheel_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entry_point: str,
) -> None:
    monkeypatch.syspath_prepend(str(_ROOT / "scripts"))
    import verify_release_package as verifier
    from release_tooling import build, common

    commands = []

    def run(args, **kwargs):
        commands.append(args)
        if "--sdist" in args:
            output = Path(args[args.index("--out-dir") + 1])
            with tarfile.open(output / "fakedetector-0.1.0.tar.gz", "w:gz") as archive:
                member = tarfile.TarInfo("fakedetector-0.1.0/graphify-out/graph.json")
                archive.addfile(member, BytesIO())
        if "ls-files" in args:
            return SimpleNamespace(stdout="README.md\0")
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(verifier, "_run", run)
    monkeypatch.setattr(common, "_run_command", run)
    if entry_point == "standalone":
        with pytest.raises(verifier.VerificationError, match="Untracked"):
            verifier.verify(tmp_path)
    else:
        with pytest.raises(common.ReleaseVerificationError, match="Untracked") as caught:
            build._build_release_inputs(
                repository=_ROOT, output=tmp_path, project_name="fakedetector", uv="uv", env={},
            )
        assert caught.value.phase == "build_sdist"
    assert not any("--wheel" in command for command in commands)


def test_runtime_constraints_are_exported_from_lock_without_dev_or_project(
    tmp_path: Path,
) -> None:
    constraints = tmp_path / "runtime-constraints.txt"

    _run(
        "uv",
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
    )

    pyproject = _load_toml(_ROOT / "pyproject.toml")
    project = pyproject["project"]
    exported = _requirements(constraints)
    exported_names = {canonicalize_name(requirement.name) for requirement in exported}
    runtime_direct_names = {
        canonicalize_name(Requirement(specification).name)
        for specification in project["dependencies"]
    }
    dev_direct_names = {
        canonicalize_name(Requirement(specification).name)
        for specification in pyproject["dependency-groups"]["dev"]
    }
    dev_only_direct_names = dev_direct_names - runtime_direct_names
    lock = _load_toml(_ROOT / "uv.lock")
    locked_versions: dict[str, set[str]] = {}
    for package in lock["package"]:
        name = canonicalize_name(package["name"])
        locked_versions.setdefault(name, set()).add(package["version"])

    assert exported
    assert canonicalize_name(project["name"]) not in exported_names
    assert exported_names.isdisjoint(dev_only_direct_names)
    assert runtime_direct_names <= exported_names
    assert canonicalize_name("fastapi") in exported_names

    exported_markers = {
        str(requirement.marker) for requirement in exported if requirement.marker is not None
    }
    assert exported_markers
    assert exported_markers <= _locked_markers(lock)

    for requirement in exported:
        [pin] = list(requirement.specifier)
        assert pin.operator == "=="
        assert not pin.version.endswith(".*")
        assert pin.version in locked_versions[canonicalize_name(requirement.name)]
