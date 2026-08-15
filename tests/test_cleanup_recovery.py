"""Stage 4 Increment 3 deterministic cleanup recovery tests."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from threading import Event, Thread
from typing import NoReturn

import pytest

import fakedetector.intake.temporary_input as temporary_input_module
import fakedetector.lifecycle.cleanup as cleanup_module
from fakedetector.config.models import AppConfig
from fakedetector.domain import (
    AnalysisStatus,
    CleanupResult,
    CleanupStatus,
    ErrorDetail,
    ImageTechnicalParameters,
    MediaType,
    ProcessingStage,
    SourceChannel,
    SourceContext,
    ValidatedFileDescriptor,
    ValidationResult,
)
from fakedetector.intake import (
    IntakeSystemError,
    LocalTemporaryInputOwner,
    Stage3Accepted,
    TemporaryInputCleanupError,
)
from fakedetector.lifecycle import (
    AnalysisContext,
    AnalysisTask,
    BoundedLocalScheduler,
    DuplicateTaskError,
    MediaRouter,
    Stage4TaskReceiver,
    TaskExecutionOutcome,
    TaskRegistry,
    WorkspaceArtifactRegistry,
    WorkspaceCleanup,
    WorkspaceJanitor,
)

_NOW = datetime(2026, 8, 15, 15, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return _NOW


class CompletedExecutor:
    def execute(self, _task: AnalysisTask) -> TaskExecutionOutcome:
        return TaskExecutionOutcome.completed()


def make_config(
    root: Path,
    *,
    cleanup_retries: int = 2,
    quarantine_enabled: bool = True,
    ttl_minutes: int = 60,
    quarantine_ttl_hours: int = 24,
) -> AppConfig:
    return AppConfig.model_validate(
        {
            "schema_version": "1.0",
            "server": {},
            "access_channels": {},
            "limits": {"max_parallel_tasks": {"image": 1, "audio": 1, "video": 1}},
            "allowed_formats": {},
            "validation": {},
            "temporary_storage": {
                "root_path": str(root),
                "cleanup_retries": cleanup_retries,
                "quarantine_enabled": quarantine_enabled,
                "ttl_minutes": ttl_minutes,
                "quarantine_ttl_hours": quarantine_ttl_hours,
            },
            "preprocessing": {},
            "analyzers": {},
            "risk_assessment": {},
            "result": {},
            "error_handling": {},
            "logging": {},
            "external_systems": {},
        }
    )


def descriptor(analysis_id: str) -> ValidatedFileDescriptor:
    return ValidatedFileDescriptor(
        original_name="sample.png",
        extension="png",
        declared_mime_type="image/png",
        detected_mime_type="image/png",
        media_type=MediaType.IMAGE,
        size_bytes=1,
        sha256="0" * 64,
        signature_match=True,
        safe_read=True,
        technical_parameters=ImageTechnicalParameters(
            width=1,
            height=1,
            format="PNG",
            color_mode="RGB",
            has_metadata=False,
        ),
    )


def make_task(root: Path, analysis_id: str) -> tuple[AnalysisTask, LocalTemporaryInputOwner]:
    owner = LocalTemporaryInputOwner(root)
    owned_source = owner.create(analysis_id)
    owner.ingest(owned_source, BytesIO(b"x"), 1)
    accepted_source = owner.transfer(owned_source)
    validated_file = descriptor(analysis_id)
    validation = ValidationResult(
        accepted=True,
        checks=[],
        errors=[],
        validated_file=validated_file,
    )
    task = AnalysisTask(
        context=AnalysisContext(
            analysis_id=analysis_id,
            created_at=_NOW,
            status=AnalysisStatus.QUEUED,
            stage=ProcessingStage.REGISTERED,
            source=SourceContext(channel=SourceChannel.API),
            workspace_path=root / analysis_id,
            media_type=MediaType.IMAGE,
            config_snapshot_id="a" * 64,
        ),
        validation=validation,
        validated_file=validated_file,
        accepted_source=accepted_source,
        artifacts=WorkspaceArtifactRegistry(root / analysis_id),
    )
    return task, owner


def register_finished_task(
    registry: TaskRegistry,
    task: AnalysisTask,
    cleanup_result: CleanupResult,
) -> None:
    analysis_id = task.context.analysis_id
    registry.reserve(task)
    registry.transition(
        analysis_id,
        status=AnalysisStatus.QUEUED,
        stage=ProcessingStage.ROUTING,
    )
    registry.bind_route(analysis_id, MediaType.IMAGE)
    registry.transition(
        analysis_id,
        status=AnalysisStatus.QUEUED,
        stage=ProcessingStage.QUEUED,
    )
    registry.mark_enqueued(analysis_id, _NOW)
    registry.claim(analysis_id, _NOW)
    registry.record_outcome(analysis_id, TaskExecutionOutcome.completed())
    registry.record_cleanup(analysis_id, cleanup_result)
    assert cleanup_result.finished_at is not None
    registry.finish(analysis_id, cleanup_result.finished_at)


@pytest.mark.parametrize(
    ("failures", "cleanup_retries", "expected_calls", "expected_status"),
    [
        (0, 2, 1, CleanupStatus.COMPLETED),
        (1, 2, 2, CleanupStatus.COMPLETED),
        (2, 2, 3, CleanupStatus.COMPLETED),
        (3, 2, 3, CleanupStatus.FAILED),
        (1, 0, 1, CleanupStatus.FAILED),
    ],
)
def test_configured_retry_matrix_is_exact_and_factual(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failures: int,
    cleanup_retries: int,
    expected_calls: int,
    expected_status: CleanupStatus,
) -> None:
    analysis_id = "1" * 32
    root = tmp_path / "temp"
    task, owner = make_task(root, analysis_id)
    config = make_config(
        root,
        cleanup_retries=cleanup_retries,
        quarantine_enabled=False,
    )
    real_cleanup = owner.cleanup
    calls = 0

    def cleanup_with_transient_failures(owned_source) -> None:
        nonlocal calls
        calls += 1
        if calls <= failures:
            raise TemporaryInputCleanupError()
        real_cleanup(owned_source)

    monkeypatch.setattr(owner, "cleanup", cleanup_with_transient_failures)

    result = WorkspaceCleanup(
        config=config.temporary_storage,
        clock=FixedClock(),
    ).cleanup_task(task)

    assert calls == expected_calls
    assert result.status is expected_status
    assert result.quarantine_used is False
    if expected_status is CleanupStatus.COMPLETED:
        assert result.original_file_deleted
        assert result.intermediate_files_deleted
        assert not (root / analysis_id).exists()
        assert result.errors == []
    else:
        assert not result.original_file_deleted
        assert not result.intermediate_files_deleted
        assert (root / analysis_id).is_dir()
        assert result.errors[0].code == "cleanup_failed"


def test_retry_preserves_deleted_artifact_fact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis_id = "2" * 32
    root = tmp_path / "temp"
    task, owner = make_task(root, analysis_id)
    artifact = root / analysis_id / "artifact.bin"
    artifact.write_bytes(b"artifact")
    task.artifacts.register("artifact", "artifact.bin")
    real_cleanup = owner.cleanup
    source_calls = 0
    unlink_calls = 0
    real_unlink = Path.unlink

    def fail_source_once(owned_source) -> None:
        nonlocal source_calls
        source_calls += 1
        if source_calls == 1:
            raise TemporaryInputCleanupError()
        real_cleanup(owned_source)

    def count_artifact_unlink(path: Path, *args, **kwargs) -> None:
        nonlocal unlink_calls
        if path == artifact:
            unlink_calls += 1
        real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(owner, "cleanup", fail_source_once)
    monkeypatch.setattr(Path, "unlink", count_artifact_unlink)
    config = make_config(root, cleanup_retries=2, quarantine_enabled=False)

    result = WorkspaceCleanup(
        config=config.temporary_storage,
        clock=FixedClock(),
    ).cleanup_task(task)

    assert result.status is CleanupStatus.COMPLETED
    assert source_calls == 2
    assert unlink_calls == 1
    assert not artifact.exists()


def test_partial_cleanup_is_factual_and_primary_status_is_independent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis_id = "3" * 32
    root = tmp_path / "temp"
    task, owner = make_task(root, analysis_id)
    config = make_config(root, cleanup_retries=0, quarantine_enabled=False)

    def delete_source_then_fail(owned_source) -> NoReturn:
        (root / analysis_id / "source").unlink()
        raise TemporaryInputCleanupError(original_file_deleted=True)

    monkeypatch.setattr(owner, "cleanup", delete_source_then_fail)

    result = WorkspaceCleanup(
        config=config.temporary_storage,
        clock=FixedClock(),
    ).cleanup_task(task)

    assert result.status is CleanupStatus.PARTIAL
    assert result.original_file_deleted
    assert not result.intermediate_files_deleted
    assert result.errors[0].code == "cleanup_failed"


def test_failed_primary_outcome_is_preserved_when_cleanup_exhausts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis_id = "0" * 32
    root = tmp_path / "temp"
    task, owner = make_task(root, analysis_id)
    config = make_config(root, cleanup_retries=0, quarantine_enabled=False)
    registry = TaskRegistry()
    registry.reserve(task)
    registry.transition(
        analysis_id,
        status=AnalysisStatus.QUEUED,
        stage=ProcessingStage.ROUTING,
    )
    registry.bind_route(analysis_id, MediaType.IMAGE)
    registry.transition(
        analysis_id,
        status=AnalysisStatus.QUEUED,
        stage=ProcessingStage.QUEUED,
    )
    registry.mark_enqueued(analysis_id, _NOW)
    claimed = registry.claim(analysis_id, _NOW)
    registry.record_outcome(
        analysis_id,
        TaskExecutionOutcome.failed(
            ErrorDetail(
                code="internal_error",
                category="internal",
                message="Внутренняя ошибка.",
                retryable=True,
            )
        ),
    )
    monkeypatch.setattr(
        owner,
        "cleanup",
        lambda _source: (_ for _ in ()).throw(TemporaryInputCleanupError()),
    )
    cleanup = WorkspaceCleanup(
        config=config.temporary_storage,
        clock=FixedClock(),
    ).cleanup_task(claimed)
    registry.record_cleanup(analysis_id, cleanup)
    registry.finish(analysis_id, _NOW)

    snapshot = registry.snapshot(analysis_id)
    assert snapshot.status is AnalysisStatus.FAILED
    assert snapshot.cleanup is not None
    assert snapshot.cleanup.status is CleanupStatus.FAILED


def test_quarantine_success_moves_remaining_workspace_without_claiming_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis_id = "4" * 32
    root = tmp_path / "temp"
    task, owner = make_task(root, analysis_id)
    config = make_config(root, cleanup_retries=2, quarantine_enabled=True)
    calls = 0

    def always_fail(_owned_source) -> NoReturn:
        nonlocal calls
        calls += 1
        raise TemporaryInputCleanupError()

    monkeypatch.setattr(owner, "cleanup", always_fail)

    result = WorkspaceCleanup(
        config=config.temporary_storage,
        clock=FixedClock(),
    ).cleanup_task(task)

    assert calls == 3
    assert result.status is CleanupStatus.FAILED
    assert result.quarantine_used
    assert not result.original_file_deleted
    assert not result.intermediate_files_deleted
    assert not (root / analysis_id).exists()
    assert (tmp_path / "quarantine" / analysis_id / "source").is_file()


def test_cleanup_after_cleanup_exhaustion_quarantine_releases_same_accepted_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis_id = "5" * 32
    root = tmp_path / "temp"
    task, owner = make_task(root, analysis_id)
    config = make_config(root, cleanup_retries=1, quarantine_enabled=True)
    real_cleanup = owner.cleanup
    cleanup_calls = 0

    def fail_initial_cleanup(_owned_source) -> NoReturn:
        nonlocal cleanup_calls
        cleanup_calls += 1
        raise TemporaryInputCleanupError()

    monkeypatch.setattr(owner, "cleanup", fail_initial_cleanup)
    result = WorkspaceCleanup(
        config=config.temporary_storage,
        clock=FixedClock(),
    ).cleanup_task(task)
    monkeypatch.setattr(owner, "cleanup", real_cleanup)
    quarantine_item = tmp_path / "quarantine" / analysis_id

    assert cleanup_calls == 2
    assert result.status is CleanupStatus.FAILED
    assert result.quarantine_used
    assert quarantine_item.is_dir()
    assert not task.accepted_source.is_released
    with task.accepted_source.open_for_read() as source:
        assert source.read() == b"x"

    task.accepted_source.cleanup()

    assert not quarantine_item.exists()
    assert task.accepted_source.is_released
    task.accepted_source.cleanup()
    assert task.accepted_source.is_released
    with pytest.raises(IntakeSystemError), task.accepted_source.open_for_read():
        pass


def test_quarantine_collision_does_not_overwrite_or_lose_either_item(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis_id = "5" * 32
    root = tmp_path / "temp"
    task, owner = make_task(root, analysis_id)
    destination = tmp_path / "quarantine" / analysis_id
    destination.mkdir(parents=True)
    unrelated = destination / "unrelated"
    unrelated.write_bytes(b"keep")
    real_cleanup = owner.cleanup
    monkeypatch.setattr(
        owner,
        "cleanup",
        lambda _source: (_ for _ in ()).throw(TemporaryInputCleanupError()),
    )
    config = make_config(root, cleanup_retries=0, quarantine_enabled=True)

    result = WorkspaceCleanup(
        config=config.temporary_storage,
        clock=FixedClock(),
    ).cleanup_task(task)

    assert result.status is CleanupStatus.FAILED
    assert not result.quarantine_used
    assert (root / analysis_id / "source").is_file()
    assert unrelated.read_bytes() == b"keep"
    assert not task.accepted_source.is_released
    with task.accepted_source.open_for_read() as source:
        assert source.read() == b"x"
    monkeypatch.setattr(owner, "cleanup", real_cleanup)
    task.accepted_source.cleanup()
    assert task.accepted_source.is_released


def test_quarantine_move_failure_retains_prior_controlled_location_and_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis_id = "6" * 32
    root = tmp_path / "temp"
    task, owner = make_task(root, analysis_id)
    config = make_config(root, cleanup_retries=0, quarantine_enabled=True)
    real_cleanup = owner.cleanup
    real_rename = Path.rename

    monkeypatch.setattr(
        owner,
        "cleanup",
        lambda _source: (_ for _ in ()).throw(TemporaryInputCleanupError()),
    )

    def fail_workspace_move(path: Path, target: Path) -> Path:
        if path == root / analysis_id:
            raise OSError("PRIVATE MOVE FAILURE")
        return real_rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_workspace_move)
    result = WorkspaceCleanup(
        config=config.temporary_storage,
        clock=FixedClock(),
    ).cleanup_task(task)

    assert result.status is CleanupStatus.FAILED
    assert not result.quarantine_used
    assert (root / analysis_id / "source").is_file()
    assert not (tmp_path / "quarantine" / analysis_id).exists()
    assert not task.accepted_source.is_released
    with task.accepted_source.open_for_read() as source:
        assert source.read() == b"x"
    monkeypatch.setattr(owner, "cleanup", real_cleanup)
    task.accepted_source.cleanup()
    assert task.accepted_source.is_released


def create_workspace(root: Path, analysis_id: str, modified_at: datetime) -> Path:
    workspace = root / analysis_id
    workspace.mkdir(parents=True)
    (workspace / "source").write_bytes(b"x")
    os.utime(workspace, (modified_at.timestamp(), modified_at.timestamp()))
    return workspace


def test_workspace_ttl_boundary_and_active_exclusion(tmp_path: Path) -> None:
    root = tmp_path / "temp"
    younger_id = "6" * 32
    exact_id = "7" * 32
    older_id = "8" * 32
    active_id = "9" * 32
    younger = create_workspace(
        root,
        younger_id,
        _NOW - timedelta(minutes=60) + timedelta(seconds=1),
    )
    exact = create_workspace(root, exact_id, _NOW - timedelta(minutes=60))
    older = create_workspace(root, older_id, _NOW - timedelta(minutes=60, seconds=1))
    active_task, _owner = make_task(root, active_id)
    os.utime(root / active_id, ((_NOW - timedelta(days=1)).timestamp(),) * 2)
    registry = TaskRegistry()
    registry.reserve(active_task)
    config = make_config(root, ttl_minutes=60, quarantine_enabled=False)

    result = WorkspaceJanitor(
        config=config.temporary_storage,
        clock=FixedClock(),
        registry=registry,
    ).sweep()

    assert younger.is_dir()
    assert not exact.exists()
    assert not older.exists()
    assert (root / active_id / "source").is_file()
    assert result.workspaces_deleted == (exact_id, older_id)


def test_workspace_retry_exhaustion_quarantines_but_not_again_in_same_sweep(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis_id = "d" * 32
    root = tmp_path / "temp"
    workspace = create_workspace(root, analysis_id, _NOW - timedelta(days=3))
    config = make_config(
        root,
        cleanup_retries=2,
        quarantine_enabled=True,
        quarantine_ttl_hours=24,
    )
    janitor = WorkspaceJanitor(
        config=config.temporary_storage,
        clock=FixedClock(),
        registry=TaskRegistry(),
    )
    real_rmtree = cleanup_module.shutil.rmtree
    calls = 0

    def fail_workspace(path: Path) -> None:
        nonlocal calls
        if path == workspace:
            calls += 1
            raise OSError("PRIVATE")
        real_rmtree(path)

    monkeypatch.setattr(cleanup_module.shutil, "rmtree", fail_workspace)

    result = janitor.sweep()

    quarantine_item = tmp_path / "quarantine" / analysis_id
    assert calls == 3
    assert result.workspaces_quarantined == (analysis_id,)
    assert result.quarantine_deleted == ()
    assert not workspace.exists()
    assert (quarantine_item / "source").is_file()
    assert datetime.fromtimestamp(quarantine_item.stat().st_mtime, UTC) == _NOW


def test_registry_cleanup_claim_closes_registration_race(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis_id = "a" * 32
    root = tmp_path / "temp"
    task, _owner = make_task(root, analysis_id)
    os.utime(root / analysis_id, ((_NOW - timedelta(days=1)).timestamp(),) * 2)
    registry = TaskRegistry()
    config = make_config(root, quarantine_enabled=False)
    janitor = WorkspaceJanitor(
        config=config.temporary_storage,
        clock=FixedClock(),
        registry=registry,
    )
    entered_cleanup = Event()
    release_cleanup = Event()
    registration_finished = Event()
    registration_errors: list[Exception] = []
    real_recover = janitor._recover_workspace

    def blocking_recover(entry: Path, candidate_id: str) -> str:
        entered_cleanup.set()
        assert release_cleanup.wait(5)
        return real_recover(entry, candidate_id)

    def register() -> None:
        try:
            registry.reserve(task)
        except Exception as error:
            registration_errors.append(error)
        finally:
            registration_finished.set()

    monkeypatch.setattr(janitor, "_recover_workspace", blocking_recover)
    sweep_thread = Thread(target=janitor.sweep)
    sweep_thread.start()
    assert entered_cleanup.wait(5)
    registration_thread = Thread(target=register)
    registration_thread.start()
    assert not registration_finished.is_set()

    release_cleanup.set()
    sweep_thread.join(5)
    registration_thread.join(5)

    assert registration_finished.is_set()
    assert len(registration_errors) == 1
    assert isinstance(registration_errors[0], DuplicateTaskError)
    assert not registry.is_active(analysis_id)
    assert not (root / analysis_id).exists()


def test_quarantine_ttl_releases_known_controlled_source_through_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis_id = "b" * 32
    root = tmp_path / "temp"
    task, owner = make_task(root, analysis_id)
    config = make_config(
        root,
        cleanup_retries=0,
        quarantine_enabled=True,
        quarantine_ttl_hours=24,
    )
    real_cleanup = owner.cleanup
    monkeypatch.setattr(
        owner,
        "cleanup",
        lambda _source: (_ for _ in ()).throw(TemporaryInputCleanupError()),
    )
    cleanup_result = WorkspaceCleanup(
        config=config.temporary_storage,
        clock=FixedClock(),
    ).cleanup_task(task)
    monkeypatch.setattr(owner, "cleanup", real_cleanup)
    quarantine_item = tmp_path / "quarantine" / analysis_id
    os.utime(quarantine_item, ((_NOW - timedelta(hours=24)).timestamp(),) * 2)
    registry = TaskRegistry()
    register_finished_task(registry, task, cleanup_result)

    result = WorkspaceJanitor(
        config=config.temporary_storage,
        clock=FixedClock(),
        registry=registry,
    ).sweep()

    assert result.quarantine_deleted == (analysis_id,)
    assert result.issues == ()
    assert not quarantine_item.exists()
    assert task.accepted_source.is_released
    task.accepted_source.cleanup()
    assert task.accepted_source.is_released
    with pytest.raises(IntakeSystemError), task.accepted_source.open_for_read():
        pass
    snapshot = registry.snapshot(analysis_id)
    assert snapshot.cleanup is not None
    assert snapshot.cleanup.status is CleanupStatus.FAILED
    assert snapshot.cleanup.quarantine_used


def test_failed_known_quarantine_ttl_cleanup_remains_controlled_and_retryable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis_id = "c" * 32
    root = tmp_path / "temp"
    task, owner = make_task(root, analysis_id)
    config = make_config(
        root,
        cleanup_retries=0,
        quarantine_enabled=True,
        quarantine_ttl_hours=24,
    )
    real_cleanup = owner.cleanup
    monkeypatch.setattr(
        owner,
        "cleanup",
        lambda _source: (_ for _ in ()).throw(TemporaryInputCleanupError()),
    )
    cleanup_result = WorkspaceCleanup(
        config=config.temporary_storage,
        clock=FixedClock(),
    ).cleanup_task(task)
    monkeypatch.setattr(owner, "cleanup", real_cleanup)
    quarantine_item = tmp_path / "quarantine" / analysis_id
    os.utime(quarantine_item, ((_NOW - timedelta(hours=24)).timestamp(),) * 2)
    registry = TaskRegistry()
    register_finished_task(registry, task, cleanup_result)
    janitor = WorkspaceJanitor(
        config=config.temporary_storage,
        clock=FixedClock(),
        registry=registry,
    )
    real_rmtree = temporary_input_module.shutil.rmtree

    def fail_controlled_cleanup(path: Path) -> NoReturn:
        assert path == quarantine_item
        raise OSError("PRIVATE QUARANTINE PATH")

    monkeypatch.setattr(temporary_input_module.shutil, "rmtree", fail_controlled_cleanup)
    first = janitor.sweep()

    assert first.quarantine_deleted == ()
    assert len(first.issues) == 1
    assert first.issues[0].analysis_id == analysis_id
    assert first.issues[0].code == "quarantine_cleanup_failed"
    assert "PRIVATE" not in repr(first)
    assert quarantine_item.is_dir()
    assert not task.accepted_source.is_released
    with task.accepted_source.open_for_read() as source:
        assert source.read() == b"x"

    monkeypatch.setattr(temporary_input_module.shutil, "rmtree", real_rmtree)
    second = janitor.sweep()

    assert second.quarantine_deleted == (analysis_id,)
    assert second.issues == ()
    assert not quarantine_item.exists()
    assert task.accepted_source.is_released


def test_orphan_quarantine_ttl_retries_once_per_sweep_and_retains_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "temp"
    quarantine = tmp_path / "quarantine"
    younger_id = "b" * 32
    eligible_id = "c" * 32
    younger = create_workspace(
        quarantine,
        younger_id,
        _NOW - timedelta(hours=24) + timedelta(seconds=1),
    )
    eligible = create_workspace(quarantine, eligible_id, _NOW - timedelta(hours=24))
    config = make_config(root, quarantine_ttl_hours=24)
    janitor = WorkspaceJanitor(
        config=config.temporary_storage,
        clock=FixedClock(),
        registry=TaskRegistry(),
    )
    calls = 0
    real_rmtree = cleanup_module.shutil.rmtree

    def fail_eligible_once(path: Path) -> None:
        nonlocal calls
        if path == eligible:
            calls += 1
            raise OSError("PRIVATE PATH")
        real_rmtree(path)

    monkeypatch.setattr(cleanup_module.shutil, "rmtree", fail_eligible_once)
    first = janitor.sweep()

    assert younger.is_dir()
    assert eligible.is_dir()
    assert calls == 1
    assert first.quarantine_deleted == ()
    assert first.issues[0].analysis_id == eligible_id
    assert "PRIVATE" not in repr(first)

    monkeypatch.setattr(cleanup_module.shutil, "rmtree", real_rmtree)
    second = janitor.sweep()

    assert second.quarantine_deleted == (eligible_id,)
    assert not eligible.exists()
    assert younger.is_dir()


def test_suspicious_entries_are_retained_and_symlink_is_not_followed(tmp_path: Path) -> None:
    root = tmp_path / "temp"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_file = outside / "keep"
    outside_file.write_bytes(b"keep")
    malformed = root / "user-supplied-name"
    malformed.mkdir()
    unexpected_file = root / ("d" * 32)
    unexpected_file.write_bytes(b"keep")
    link = root / ("e" * 32)
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is not available in this environment")
    config = make_config(root)

    result = WorkspaceJanitor(
        config=config.temporary_storage,
        clock=FixedClock(),
        registry=TaskRegistry(),
    ).sweep()

    assert malformed.is_dir()
    assert unexpected_file.read_bytes() == b"keep"
    assert link.is_symlink()
    assert outside_file.read_bytes() == b"keep"
    assert len(result.issues) == 3
    assert all(issue.analysis_id is None for issue in result.issues)


def test_scheduler_invokes_startup_post_terminal_and_shutdown_sweeps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "temp"
    config = make_config(root, quarantine_enabled=False)
    registry = TaskRegistry()
    sweep_calls = 0
    real_sweep = WorkspaceJanitor.sweep

    def count_sweep(janitor: WorkspaceJanitor):
        nonlocal sweep_calls
        sweep_calls += 1
        return real_sweep(janitor)

    monkeypatch.setattr(WorkspaceJanitor, "sweep", count_sweep)
    executor = CompletedExecutor()
    scheduler = BoundedLocalScheduler(config=config, clock=FixedClock(), registry=registry)
    receiver = Stage4TaskReceiver(
        config=config,
        clock=FixedClock(),
        registry=registry,
        router=MediaRouter(dict.fromkeys(MediaType, executor)),
        queue=scheduler,
    )
    scheduler.start()
    analysis_id = "f" * 32
    task, owner = make_task(root, analysis_id)
    accepted = Stage3Accepted(
        analysis_id=analysis_id,
        registered_at=_NOW,
        source=task.context.source,
        validation=task.validation,
        validated_file=task.validated_file,
        controlled_source=task.accepted_source,
    )
    receiver.accept(accepted)
    scheduler.shutdown(drain=True)

    assert registry.snapshot(analysis_id).status is AnalysisStatus.COMPLETED
    assert not (root / analysis_id).exists()
    assert sweep_calls == 3
    assert owner is not None
