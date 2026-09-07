"""Internal capability and immutable model tests for Stage 5 Increment 1."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path, PurePath
from typing import cast

import pytest

import fakedetector
import fakedetector.intake as intake
import fakedetector.lifecycle as lifecycle
import fakedetector.preprocessing as preprocessing
from fakedetector.domain import (
    AnalysisStatus,
    ImageTechnicalParameters,
    MediaType,
    ProcessingStage,
    SourceChannel,
    SourceContext,
    ValidatedFileDescriptor,
    ValidationResult,
)
from fakedetector.intake import AcceptedSource, LocalTemporaryInputOwner
from fakedetector.intake.temporary_input import PreparedSourceRef
from fakedetector.lifecycle import AnalysisContext, AnalysisTask, TaskSnapshot
from fakedetector.lifecycle.artifacts import WorkspaceArtifactRegistry
from fakedetector.lifecycle.models import Stage5TaskData, _StoredAnalyzerResult
from fakedetector.preprocessing._models import PreparedArtifact, PreparedMedia

_CREATED_AT = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)


def make_accepted_source(root: Path, analysis_id: str) -> AcceptedSource:
    owner = LocalTemporaryInputOwner(root)
    owned_source = owner.create(analysis_id)
    owner.ingest(owned_source, BytesIO(b"source"), 100)
    return owner.transfer(owned_source)


def make_prepared_media(
    root: Path,
    analysis_id: str,
    *,
    media_type: MediaType = MediaType.IMAGE,
    metadata: dict[str, object] | None = None,
    warnings: list[str] | None = None,
) -> tuple[PreparedMedia, PreparedArtifact, AcceptedSource, WorkspaceArtifactRegistry]:
    accepted_source = make_accepted_source(root, analysis_id)
    registry = WorkspaceArtifactRegistry(root / analysis_id)
    artifact_ref = registry.register("normalized_image", "normalized.png")
    artifact = PreparedArtifact(
        artifact_id="normalized_image",
        artifact_type="normalized_image",
        artifact_ref=artifact_ref,
        format="png",
        cleanup_required=True,
    )
    prepared_media = PreparedMedia(
        analysis_id=analysis_id,
        media_type=media_type,
        source_file_ref=PreparedSourceRef(accepted_source),
        artifacts=(artifact,),
        metadata=metadata or {},
        warnings=warnings or [],
    )
    return prepared_media, artifact, accepted_source, registry


def image_descriptor(analysis_id: str) -> ValidatedFileDescriptor:
    return ValidatedFileDescriptor(
        original_name=f"{analysis_id}.png",
        extension="png",
        declared_mime_type="image/png",
        detected_mime_type="image/png",
        media_type=MediaType.IMAGE,
        size_bytes=6,
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


def make_task(
    root: Path,
    analysis_id: str,
    accepted_source: AcceptedSource,
    artifacts: WorkspaceArtifactRegistry,
    stage5_data: Stage5TaskData,
) -> AnalysisTask:
    descriptor = image_descriptor(analysis_id)
    validation = ValidationResult(
        accepted=True,
        checks=[],
        errors=[],
        validated_file=descriptor,
    )
    return AnalysisTask(
        context=AnalysisContext(
            analysis_id=analysis_id,
            created_at=_CREATED_AT,
            status=AnalysisStatus.QUEUED,
            stage=ProcessingStage.REGISTERED,
            source=SourceContext(channel=SourceChannel.API),
            workspace_path=root / analysis_id,
            media_type=MediaType.IMAGE,
            config_snapshot_id="a" * 64,
        ),
        validation=validation,
        validated_file=descriptor,
        accepted_source=accepted_source,
        artifacts=artifacts,
        stage5_data=stage5_data,
    )


def cleanup_prepared(
    accepted_source: AcceptedSource,
    registry: WorkspaceArtifactRegistry,
) -> None:
    assert registry.cleanup_once().completed
    accepted_source.cleanup()


def test_stage5_internal_types_do_not_expand_public_exports() -> None:
    for module, internal_names in (
        (
            fakedetector,
            (
                "PreparedSourceRef",
                "WorkspaceArtifactRef",
                "Stage5TaskData",
                "_StoredAnalyzerResult",
                "_read_stage5_analyzer_results",
            ),
        ),
        (intake, ("PreparedSourceRef",)),
        (
            lifecycle,
            (
                "WorkspaceArtifactRef",
                "Stage5TaskData",
                "_StoredAnalyzerResult",
                "_read_stage5_analyzer_results",
            ),
        ),
        (preprocessing, ("PreparedArtifact", "PreparedMedia")),
    ):
        assert not any(hasattr(module, name) for name in internal_names)


@pytest.mark.parametrize("mutable_json", [bytearray(b"{}"), memoryview(b"{}")])
def test_stored_analyzer_result_rejects_non_bytes_storage(mutable_json: object) -> None:
    with pytest.raises(TypeError, match="immutable bytes"):
        _StoredAnalyzerResult(
            analyzer_id="fake_image_analyzer",
            media_type=MediaType.IMAGE,
            canonical_json=cast(bytes, mutable_json),
        )


def test_prepared_models_are_immutable_defensive_and_path_free(tmp_path: Path) -> None:
    metadata: dict[str, object] = {"camera": {"tags": ["original"]}}
    warnings = ["first-frame representation"]
    prepared, artifact, accepted_source, registry = make_prepared_media(
        tmp_path / "temp",
        "a" * 32,
        metadata=metadata,
        warnings=warnings,
    )
    artifact_alias = [artifact]
    prepared_from_aliases = PreparedMedia(
        analysis_id=prepared.analysis_id,
        media_type=prepared.media_type,
        source_file_ref=prepared.source_file_ref,
        artifacts=artifact_alias,
        metadata=metadata,
        warnings=warnings,
    )

    cast(dict[str, object], metadata["camera"])["tags"] = ["mutated"]
    metadata["new"] = "caller-only"
    warnings.append("caller-only")
    artifact_alias.clear()

    assert prepared_from_aliases.artifacts == (artifact,)
    assert prepared_from_aliases.metadata == {"camera": {"tags": ("original",)}}
    assert prepared_from_aliases.warnings == ("first-frame representation",)
    with pytest.raises(TypeError):
        cast(dict[str, object], prepared_from_aliases.metadata)["new"] = "blocked"
    with pytest.raises(FrozenInstanceError):
        artifact.format = "jpeg"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        prepared_from_aliases.analysis_id = "changed"  # type: ignore[misc]

    assert not any(
        isinstance(getattr(artifact, model_field.name), PurePath)
        for model_field in fields(PreparedArtifact)
    )
    assert not any(
        hasattr(value, attribute)
        for value in (artifact, prepared_from_aliases)
        for attribute in ("path", "physical_path", "workspace_path")
    )
    assert str(tmp_path) not in repr(artifact)
    assert str(tmp_path) not in repr(prepared_from_aliases)

    cleanup_prepared(accepted_source, registry)


def test_prepared_media_rejects_source_mismatch_and_conflicting_artifact_ids(
    tmp_path: Path,
) -> None:
    prepared, artifact, accepted_source, registry = make_prepared_media(
        tmp_path / "temp",
        "b" * 32,
    )

    with pytest.raises(ValueError, match="source identity"):
        PreparedMedia(
            analysis_id="c" * 32,
            media_type=MediaType.IMAGE,
            source_file_ref=prepared.source_file_ref,
        )
    with pytest.raises(ValueError, match="conflicting IDs"):
        PreparedMedia(
            analysis_id=prepared.analysis_id,
            media_type=MediaType.IMAGE,
            source_file_ref=prepared.source_file_ref,
            artifacts=(artifact, artifact),
        )

    cleanup_prepared(accepted_source, registry)


@pytest.mark.parametrize(
    "unsafe_metadata",
    [Path("metadata.txt"), PurePath("metadata.txt"), b"binary", bytearray(b"binary")],
    ids=["path", "pure-path", "bytes", "bytearray"],
)
def test_prepared_media_rejects_path_and_binary_metadata(
    tmp_path: Path,
    unsafe_metadata: object,
) -> None:
    analysis_id = "c" * 32
    accepted_source = make_accepted_source(tmp_path / "temp", analysis_id)

    with pytest.raises(TypeError, match="paths or binary data"):
        PreparedMedia(
            analysis_id=analysis_id,
            media_type=MediaType.IMAGE,
            source_file_ref=PreparedSourceRef(accepted_source),
            metadata={"unsafe": unsafe_metadata},
        )

    accepted_source.cleanup()


def test_stage5_task_data_is_hidden_from_task_snapshot(tmp_path: Path) -> None:
    root = tmp_path / "temp"
    analysis_id = "d" * 32
    prepared, _artifact, accepted_source, registry = make_prepared_media(root, analysis_id)
    stage5_data = Stage5TaskData(prepared_media=prepared, analyzer_results=[])
    task = make_task(root, analysis_id, accepted_source, registry, stage5_data)

    snapshot = task.snapshot()

    assert task.stage5_data is stage5_data
    assert stage5_data.analyzer_results == ()
    assert "stage5_data" not in {model_field.name for model_field in fields(TaskSnapshot)}
    assert not hasattr(snapshot, "stage5_data")
    assert str(tmp_path) not in repr(snapshot)

    cleanup_prepared(accepted_source, registry)


def test_analysis_task_rejects_stage5_analysis_id_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "temp"
    task_id = "e" * 32
    stage5_id = "f" * 32
    _task_prepared, _artifact, task_source, task_registry = make_prepared_media(root, task_id)
    stage5_prepared, _artifact, stage5_source, stage5_registry = make_prepared_media(
        root,
        stage5_id,
    )

    with pytest.raises(ValueError, match="Stage 5 identity"):
        make_task(
            root,
            task_id,
            task_source,
            task_registry,
            Stage5TaskData(prepared_media=stage5_prepared),
        )

    cleanup_prepared(task_source, task_registry)
    cleanup_prepared(stage5_source, stage5_registry)


def test_analysis_task_rejects_stage5_media_type_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "temp"
    analysis_id = "1" * 32
    prepared, _artifact, accepted_source, registry = make_prepared_media(
        root,
        analysis_id,
        media_type=MediaType.AUDIO,
    )

    with pytest.raises(ValueError, match="Stage 5 media type"):
        make_task(
            root,
            analysis_id,
            accepted_source,
            registry,
            Stage5TaskData(prepared_media=prepared),
        )

    cleanup_prepared(accepted_source, registry)


def test_analysis_task_rejects_different_source_capability_with_same_analysis_id(
    tmp_path: Path,
) -> None:
    analysis_id = "2" * 32
    task_root = tmp_path / "task"
    _prepared, artifact, task_source, task_registry = make_prepared_media(
        task_root,
        analysis_id,
    )
    foreign_source = make_accepted_source(tmp_path / "foreign", analysis_id)
    foreign_prepared = PreparedMedia(
        analysis_id=analysis_id,
        media_type=MediaType.IMAGE,
        source_file_ref=PreparedSourceRef(foreign_source),
        artifacts=(artifact,),
    )

    with pytest.raises(ValueError, match="source capability"):
        make_task(
            task_root,
            analysis_id,
            task_source,
            task_registry,
            Stage5TaskData(prepared_media=foreign_prepared),
        )

    cleanup_prepared(task_source, task_registry)
    foreign_source.cleanup()


def test_analysis_task_rejects_artifact_ref_from_foreign_registry(tmp_path: Path) -> None:
    analysis_id = "3" * 32
    task_root = tmp_path / "task"
    prepared, _artifact, accepted_source, task_registry = make_prepared_media(
        task_root,
        analysis_id,
    )
    foreign_registry = WorkspaceArtifactRegistry(tmp_path / "foreign")
    foreign_ref = foreign_registry.register("normalized_image", "normalized.png")
    foreign_artifact = PreparedArtifact(
        artifact_id="normalized_image",
        artifact_type="normalized_image",
        artifact_ref=foreign_ref,
        format="png",
    )
    foreign_prepared = PreparedMedia(
        analysis_id=analysis_id,
        media_type=MediaType.IMAGE,
        source_file_ref=prepared.source_file_ref,
        artifacts=(foreign_artifact,),
    )

    with pytest.raises(ValueError, match="artifact capability"):
        make_task(
            task_root,
            analysis_id,
            accepted_source,
            task_registry,
            Stage5TaskData(prepared_media=foreign_prepared),
        )

    cleanup_prepared(accepted_source, task_registry)
    assert foreign_registry.cleanup_once().completed


def test_analysis_task_rejects_artifact_id_that_does_not_match_ref(tmp_path: Path) -> None:
    analysis_id = "4" * 32
    task_root = tmp_path / "task"
    prepared, artifact, accepted_source, registry = make_prepared_media(task_root, analysis_id)
    mismatched_artifact = PreparedArtifact(
        artifact_id="declared_other_artifact",
        artifact_type=artifact.artifact_type,
        artifact_ref=artifact.artifact_ref,
        format=artifact.format,
    )
    mismatched_prepared = PreparedMedia(
        analysis_id=analysis_id,
        media_type=MediaType.IMAGE,
        source_file_ref=prepared.source_file_ref,
        artifacts=(mismatched_artifact,),
    )

    with pytest.raises(ValueError, match="artifact capability"):
        make_task(
            task_root,
            analysis_id,
            accepted_source,
            registry,
            Stage5TaskData(prepared_media=mismatched_prepared),
        )

    cleanup_prepared(accepted_source, registry)
