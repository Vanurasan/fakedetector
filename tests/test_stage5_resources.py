"""Stage 5 generated-artifact capability and physical-extent bounds."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import cast

import pytest
import yaml
from pydantic import ValidationError

from fakedetector._stage5_resources import (
    _GeneratedArtifactBudget,
    _GeneratedArtifactLimitError,
    _GeneratedArtifactWriteError,
)
from fakedetector.config._snapshot import _ConfigSnapshot
from fakedetector.config.models import AppConfig
from fakedetector.domain import MediaType
from fakedetector.lifecycle.artifacts import WorkspaceArtifactRegistry

_MEBIBYTE = 1_048_576


def _config(*, image_max_mb: int = 1) -> AppConfig:
    raw = yaml.safe_load(Path("config/config.example.yaml").read_text(encoding="utf-8"))
    raw["limits"]["max_file_size_mb"]["image"] = image_max_mb
    return AppConfig.model_validate(raw)


def _image_budget(config: AppConfig | None = None) -> _GeneratedArtifactBudget:
    return _GeneratedArtifactBudget(
        _ConfigSnapshot.capture(config or _config()),
        MediaType.IMAGE,
    )


def test_config_snapshot_rejects_unvalidated_or_incoherent_construction() -> None:
    with pytest.raises(TypeError, match="requires AppConfig"):
        _ConfigSnapshot.capture(cast(AppConfig, object()))
    with pytest.raises(TypeError, match="immutable bytes"):
        _ConfigSnapshot(cast(bytes, bytearray(b"{}")), "0" * 64)
    with pytest.raises(ValueError, match="does not match"):
        _ConfigSnapshot(b"{}", "0" * 64)

    invalid_json = b"{}"
    invalid_snapshot = _ConfigSnapshot(
        invalid_json,
        hashlib.sha256(invalid_json).hexdigest(),
    )
    with pytest.raises(ValidationError):
        invalid_snapshot.materialize()


def test_generated_budget_uses_the_same_immutable_content_snapshot() -> None:
    config = _config(image_max_mb=1)
    snapshot = _ConfigSnapshot.capture(config)
    equal_snapshot = _ConfigSnapshot.capture(config.model_copy(deep=True))
    budget = _GeneratedArtifactBudget(snapshot, MediaType.IMAGE)

    config.limits.max_file_size_mb.image = 2

    assert budget.max_bytes == _MEBIBYTE
    assert budget.matches(equal_snapshot, MediaType.IMAGE)
    assert not budget.matches(_ConfigSnapshot.capture(config), MediaType.IMAGE)
    assert not budget.matches(equal_snapshot, MediaType.AUDIO)


def test_generated_budget_accepts_exact_cumulative_physical_extent(
    tmp_path: Path,
) -> None:
    budget = _image_budget()
    target = tmp_path / "exact.bin"

    with budget.open_output(target) as output:
        for _ in range(16):
            assert output.write(b"x" * (64 * 1024)) == 64 * 1024

    assert target.stat().st_size == _MEBIBYTE
    assert budget.used_bytes == budget.max_bytes == _MEBIBYTE
    assert budget.remaining_bytes == 0


def test_limit_plus_one_leaves_registered_partial_artifact_for_cleanup(
    tmp_path: Path,
) -> None:
    registry = WorkspaceArtifactRegistry(tmp_path / "workspace")
    artifact_ref = registry.register("bounded_output", "preprocessing/output.bin")
    target = registry.cleanup_obligations()[0]
    budget = _image_budget()

    def exceed_budget(path: Path) -> None:
        with budget.open_output(path) as output:
            output.write(b"x" * _MEBIBYTE)
            output.write(b"x")

    with pytest.raises(_GeneratedArtifactLimitError):
        registry.with_local_artifact_path(artifact_ref, exceed_budget)

    assert registry.cleanup_obligations() == (target,)
    assert target.stat().st_size == _MEBIBYTE
    assert registry.cleanup_once().completed
    assert not target.exists()


def test_budget_counts_maximum_extent_not_seek_overwrite_volume(tmp_path: Path) -> None:
    budget = _image_budget()
    target = tmp_path / "seekable.bin"

    with budget.open_output(target) as output:
        output.write(b"0123456789")
        output.seek(0)
        output.write(b"abcdefghij")
        output.seek(20)
        output.write(b"x")

    assert target.stat().st_size == 21
    assert budget.used_bytes == 21


def test_budget_validates_capability_and_preflight_inputs(tmp_path: Path) -> None:
    snapshot = _ConfigSnapshot.capture(_config())
    with pytest.raises(TypeError, match="config snapshot"):
        _GeneratedArtifactBudget(cast(_ConfigSnapshot, object()), MediaType.IMAGE)
    with pytest.raises(TypeError, match="media type"):
        _GeneratedArtifactBudget(snapshot, cast(MediaType, "image"))

    budget = _GeneratedArtifactBudget(snapshot, MediaType.IMAGE)
    budget.ensure_feasible(0)
    budget.ensure_feasible(_MEBIBYTE)
    with pytest.raises(TypeError, match="integer"):
        budget.ensure_feasible(cast(int, True))
    with pytest.raises(TypeError, match="integer"):
        budget.ensure_feasible(cast(int, 1.5))
    with pytest.raises(ValueError, match="negative"):
        budget.ensure_feasible(-1)
    with pytest.raises(_GeneratedArtifactLimitError):
        budget.ensure_feasible(_MEBIBYTE + 1)

    existing = tmp_path / "existing.bin"
    existing.write_bytes(b"existing")
    with pytest.raises(_GeneratedArtifactWriteError), budget.open_output(existing):
        pass


def test_bounded_writer_exposes_only_seekable_write_operations(tmp_path: Path) -> None:
    budget = _image_budget()
    target = tmp_path / "writer.bin"

    with budget.open_output(target) as output:
        assert output.closed is False
        assert output.writable() is True
        assert output.seekable() is True
        assert output.readable() is False
        assert isinstance(output.fileno(), int)
        output.write(b"0123456789")
        assert output.tell() == 10
        output.seek(5)
        assert output.truncate() == 5
        assert budget.used_bytes == 10
        output.seek(15)
        assert output.truncate() == 15
        assert budget.used_bytes == 15
        output.flush()
        with pytest.raises(ValueError, match="negative"):
            output.truncate(-1)

    assert output.closed is True
    output.close()
