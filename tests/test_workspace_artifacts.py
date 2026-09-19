"""Artifact ownership, path rejection, and physical cleanup invariants."""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import pytest

from fakedetector.lifecycle import ArtifactRegistrationError, WorkspaceArtifactRegistry


@pytest.mark.parametrize(
    ("artifact_id", "relative_path"),
    [
        ("frame", "../outside.bin"),
        ("frame", "C:\\outside.bin"),
        ("user/name", "frames/001.png"),
        ("frame", "CON"),
        ("frame", "con.png"),
        ("frame", "nested/AUX.txt"),
        ("frame", "COM1.bin"),
        ("frame", "lpt9.log"),
        ("frame", "output./child.png"),
        ("frame", "output /child.png"),
        ("frame", "nested/output."),
        ("frame", "nested/output "),
        ("frame", "output:stream"),
        ("frame", "nested/../outside.bin"),
        ("frame", "output\u00e9.png"),
    ],
)
def test_artifact_registry_rejects_user_controlled_paths(
    tmp_path: Path,
    artifact_id: str,
    relative_path: str,
) -> None:
    registry = WorkspaceArtifactRegistry(tmp_path / "workspace")
    with pytest.raises(ArtifactRegistrationError):
        registry.register(artifact_id, relative_path)
    assert registry.cleanup_obligations() == ()
    assert not (tmp_path / "workspace").exists()


@pytest.mark.parametrize(
    ("original", "alias"),
    [
        ("output", "output."),
        ("output", "output "),
        ("output", "OUTPUT"),
        ("Frames/Output.png", "frames/output.PNG"),
        ("Frames/Output.png", "FRAMES/Output.png"),
    ],
)
def test_artifact_registry_rejects_windows_alias_before_write(
    tmp_path: Path, original: str, alias: str
) -> None:
    workspace = tmp_path / "workspace"
    registry = WorkspaceArtifactRegistry(workspace)
    original_ref = registry.register("original", original)

    with pytest.raises(ArtifactRegistrationError):
        alias_ref = registry.register("alias", alias)
        registry.with_local_artifact_path(alias_ref, lambda path: path.write_bytes(b"alias"))

    assert registry.cleanup_obligations() == (workspace / original,)
    assert not workspace.exists()
    workspace.mkdir()
    assert (
        registry.with_local_artifact_path(original_ref, lambda path: path) == workspace / original
    )
    workspace.rmdir()
    # A rejected target must not consume the ID or create a cleanup obligation.
    registry.register("alias", "distinct.png")
    assert registry.cleanup_once().completed


def test_artifact_registry_allows_distinct_siblings_and_nested_paths(tmp_path: Path) -> None:
    registry = WorkspaceArtifactRegistry(tmp_path)
    relative_paths = (
        "output",
        "output.png",
        "outputs/one.png",
        "outputs/two.png",
        "outputs/deep/x.png",
    )
    refs = [
        registry.register(f"artifact_{index}", path) for index, path in enumerate(relative_paths)
    ]
    assert registry.cleanup_obligations() == tuple(tmp_path / path for path in relative_paths)
    assert list(tmp_path.iterdir()) == []

    def write(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(path.name.encode("ascii"))

    for ref in refs:
        registry.with_local_artifact_path(ref, write)
    for ref, relative_path in zip(refs, relative_paths, strict=True):
        assert registry.with_local_artifact_path(ref, lambda path: path.read_bytes()) == Path(
            relative_path
        ).name.encode("ascii")
    assert registry.cleanup_once().completed
    assert list(tmp_path.iterdir()) == []


def test_artifact_registry_tracks_and_cleans_application_obligations(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    artifact = workspace / "frames" / "001.png"
    workspace.mkdir()
    registry = WorkspaceArtifactRegistry(workspace)
    artifact_ref = registry.register("frame_001", "frames/001.png")

    assert not artifact.exists()

    def create_artifact(path: Path) -> None:
        path.parent.mkdir()
        path.write_bytes(b"generated")

    registry.with_local_artifact_path(artifact_ref, create_artifact)

    assert registry.cleanup_obligations() == (artifact,)
    assert registry.cleanup_once().completed
    assert not artifact.exists()


def test_artifact_registry_rejects_foreign_ref_and_duplicate_target(tmp_path: Path) -> None:
    first = WorkspaceArtifactRegistry(tmp_path / "first")
    second = WorkspaceArtifactRegistry(tmp_path / "second")
    artifact_ref = first.register("frame_001", "frames/001.png")

    with pytest.raises(ArtifactRegistrationError):
        second.with_local_artifact_path(artifact_ref, lambda path: path)
    with pytest.raises(ArtifactRegistrationError):
        first.register("frame_002", "frames/001.png")


def test_completed_or_missing_artifact_obligation_cannot_reopen(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    registry = WorkspaceArtifactRegistry(workspace)
    artifact_ref = registry.register("missing_artifact", "missing.bin")

    assert registry.cleanup_once().completed
    assert registry.cleanup_obligations() == (workspace / "missing.bin",)
    with pytest.raises(ArtifactRegistrationError):
        registry.with_local_artifact_path(artifact_ref, lambda path: path)


def test_artifact_obligation_survives_failure_during_physical_creation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifact = workspace / "partial.bin"
    registry = WorkspaceArtifactRegistry(workspace)
    artifact_ref = registry.register("partial_artifact", "partial.bin")

    def fail_after_partial_create(path: Path) -> NoReturn:
        path.write_bytes(b"partial")
        raise OSError("creation failed")

    with pytest.raises(OSError, match="creation failed"):
        registry.with_local_artifact_path(artifact_ref, fail_after_partial_create)

    assert registry.cleanup_obligations() == (artifact,)
    assert registry.cleanup_once().completed
    assert not artifact.exists()


def test_artifact_registry_rejects_substituted_intermediate_symlink(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "keep"
    sentinel.write_bytes(b"outside")
    frames = workspace / "frames"
    try:
        frames.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation is unavailable on this host")
    registry = WorkspaceArtifactRegistry(workspace)
    artifact_ref = registry.register("frame", "frames/output.png")

    with pytest.raises(ArtifactRegistrationError):
        registry.with_local_artifact_path(
            artifact_ref,
            lambda path: path.write_bytes(b"unsafe"),
        )

    assert frames.is_symlink()
    assert sentinel.read_bytes() == b"outside"
    assert not (outside / "output.png").exists()
    assert not registry.cleanup_once().completed
