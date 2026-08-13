"""Integrated behavior tests for the complete adapter-neutral Stage 3 lifecycle."""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import NoReturn

import pytest

import fakedetector.intake.temporary_input as temporary_input_module
from fakedetector.config.models import AppConfig
from fakedetector.domain import (
    AnalysisStatus,
    CleanupStatus,
    CompletenessStatus,
    MediaType,
    ProcessingStage,
    SourceChannel,
    SourceContext,
)
from fakedetector.intake import (
    ControlledIntakeService,
    FileIntakeService,
    FileValidator,
    IntakeSystemError,
    LocalTemporaryInputOwner,
    PreRegistrationError,
    Stage3Accepted,
    Stage3Terminal,
    ValidationSystemError,
)

_REGISTERED_AT = datetime(2026, 8, 13, 10, 30, tzinfo=UTC)


class FixedIdGenerator:
    def __init__(self, analysis_id: str = "integrated-stage3") -> None:
        self.analysis_id = analysis_id

    def generate(self) -> str:
        return self.analysis_id


class FailingIdGenerator:
    def generate(self) -> str:
        raise RuntimeError("PRIVATE ID FAILURE")


class FixedClock:
    def __init__(self, timestamp: datetime = _REGISTERED_AT) -> None:
        self.timestamp = timestamp

    def now(self) -> datetime:
        return self.timestamp


class RecordingReceiver:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0
        self.accepted: Stage3Accepted | None = None

    def accept(self, accepted: Stage3Accepted) -> None:
        self.calls += 1
        self.accepted = accepted
        if self.fail:
            raise RuntimeError("PRIVATE RECEIVER FAILURE")


class PartialThenFailStream:
    def __init__(self) -> None:
        self.calls = 0

    def read(self, size: int, /) -> bytes:
        self.calls += 1
        if self.calls == 1:
            return b"partial"[:size]
        raise OSError("PRIVATE STREAM FAILURE")


def make_config(
    root: Path,
    *,
    image_limit: int = 20,
    audio_limit: int = 50,
    video_limit: int = 200,
) -> AppConfig:
    return AppConfig.model_validate(
        {
            "schema_version": "1.0",
            "server": {},
            "access_channels": {},
            "limits": {
                "max_file_size_mb": {
                    "image": image_limit,
                    "audio": audio_limit,
                    "video": video_limit,
                }
            },
            "allowed_formats": {},
            "validation": {},
            "temporary_storage": {"root_path": str(root)},
            "preprocessing": {},
            "analyzers": {},
            "risk_assessment": {},
            "result": {},
            "error_handling": {},
            "logging": {},
            "external_systems": {},
        }
    )


def make_service(
    tmp_path: Path,
    *,
    receiver: RecordingReceiver | None = None,
    analysis_id_generator: object | None = None,
    validator: object | None = None,
    image_limit: int = 20,
    audio_limit: int = 50,
    video_limit: int = 200,
) -> tuple[FileIntakeService, LocalTemporaryInputOwner, RecordingReceiver]:
    root = tmp_path / "PRIVATE-TEMP"
    config = make_config(
        root,
        image_limit=image_limit,
        audio_limit=audio_limit,
        video_limit=video_limit,
    )
    owner = LocalTemporaryInputOwner(root, chunk_size=64 * 1024)
    clock = FixedClock()
    controlled_intake = ControlledIntakeService(
        config=config,
        analysis_id_generator=analysis_id_generator or FixedIdGenerator(),  # type: ignore[arg-type]
        clock=clock,
        temporary_input_owner=owner,
    )
    actual_receiver = receiver or RecordingReceiver()
    actual_validator = validator or FileValidator(
        config=config,
        temporary_input_owner=owner,
    )
    return (
        FileIntakeService(
            controlled_intake=controlled_intake,
            validator=actual_validator,  # type: ignore[arg-type]
            temporary_input_owner=owner,
            accepted_receiver=actual_receiver,
            clock=clock,
        ),
        owner,
        actual_receiver,
    )


def source_context() -> SourceContext:
    return SourceContext(
        channel=SourceChannel.API,
        connector="mail_connector",
        external_system="gateway",
        external_reference="message-1",
    )


def assert_no_analysis_outputs(outcome: Stage3Terminal) -> None:
    assert outcome.stage is ProcessingStage.FINISHED
    assert outcome.analyzers == []
    assert outcome.findings == []
    assert outcome.completeness is CompletenessStatus.NOT_ASSESSED
    assert outcome.final_risk_level is None
    assert outcome.recommendation is None


@pytest.mark.parametrize(
    ("extension", "media_type"),
    [("png", MediaType.IMAGE), ("wav", MediaType.AUDIO), ("mp4", MediaType.VIDEO)],
)
def test_representative_media_complete_accepted_handoff(
    tmp_path: Path,
    media_files: dict[str, Path],
    extension: str,
    media_type: MediaType,
) -> None:
    service, owner, receiver = make_service(tmp_path)
    source = source_context()

    outcome = service.process(
        BytesIO(media_files[extension].read_bytes()),
        original_name=f"sample.{extension}",
        declared_content_type=None,
        source=source,
    )

    assert isinstance(outcome, Stage3Accepted)
    assert outcome.analysis_id == "integrated-stage3"
    assert outcome.registered_at is _REGISTERED_AT
    assert outcome.source is source
    assert outcome.validation.accepted
    assert outcome.validation.validated_file is outcome.validated_file
    assert outcome.validated_file.media_type is media_type
    assert receiver.calls == 1
    assert receiver.accepted is outcome
    assert (tmp_path / "PRIVATE-TEMP" / outcome.analysis_id).is_dir()
    with outcome.controlled_source.open_for_read() as controlled:
        assert controlled.read(1)
    assert not hasattr(outcome.controlled_source, "source_path")
    assert not hasattr(outcome, "cleanup")
    assert not hasattr(outcome, "risk_assessment")

    outcome.controlled_source.cleanup()
    assert not (tmp_path / "PRIVATE-TEMP" / outcome.analysis_id).exists()
    del owner


def test_accepted_outcome_enforces_validation_invariants(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    service, _owner, _receiver = make_service(tmp_path)
    outcome = service.process(
        BytesIO(media_files["png"].read_bytes()),
        original_name="sample.png",
        declared_content_type=None,
        source=source_context(),
    )
    assert isinstance(outcome, Stage3Accepted)

    rejected_validation = outcome.validation.model_copy(
        update={"accepted": False, "validated_file": None}
    )
    with pytest.raises(ValueError, match="successful validation"):
        replace(outcome, validation=rejected_validation)

    mismatched_descriptor = outcome.validated_file.model_copy(update={"original_name": "other.png"})
    with pytest.raises(ValueError, match="must match validation"):
        replace(outcome, validated_file=mismatched_descriptor)

    outcome.controlled_source.cleanup()


def test_terminal_outcome_enforces_status_and_primary_error(tmp_path: Path) -> None:
    service, _owner, _receiver = make_service(tmp_path)
    outcome = service.process(
        BytesIO(b""),
        original_name="empty.png",
        declared_content_type=None,
        source=source_context(),
    )
    assert isinstance(outcome, Stage3Terminal)

    with pytest.raises(ValueError, match="rejected or failed"):
        replace(outcome, status=AnalysisStatus.RUNNING)
    with pytest.raises(ValueError, match="primary error"):
        replace(outcome, errors=[])


@pytest.mark.parametrize(
    ("payload", "original_name", "declared_type", "error_code"),
    [
        (b"", "empty.png", None, "file_empty"),
        (b"content", "file", None, "missing_extension"),
        (b"PK\x03\x04", "archive.zip", None, "unsupported_extension"),
    ],
)
def test_normative_rejection_preserves_validation_and_cleans_once(
    tmp_path: Path,
    payload: bytes,
    original_name: str,
    declared_type: str | None,
    error_code: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, owner, receiver = make_service(tmp_path)
    cleanup_calls = 0
    real_cleanup = owner.cleanup

    def tracking_cleanup(owned_source) -> None:
        nonlocal cleanup_calls
        cleanup_calls += 1
        real_cleanup(owned_source)

    monkeypatch.setattr(owner, "cleanup", tracking_cleanup)

    outcome = service.process(
        BytesIO(payload),
        original_name=original_name,
        declared_content_type=declared_type,
        source=source_context(),
    )

    assert isinstance(outcome, Stage3Terminal)
    assert outcome.status is AnalysisStatus.REJECTED
    assert outcome.validation is not None
    assert not outcome.validation.accepted
    assert outcome.errors[0].code == error_code
    assert outcome.cleanup is not None
    assert outcome.cleanup.status is CleanupStatus.COMPLETED
    assert cleanup_calls == 1
    assert receiver.calls == 0
    assert not (tmp_path / "PRIVATE-TEMP" / outcome.analysis_id).exists()
    assert_no_analysis_outputs(outcome)


def test_declared_mime_mismatch_and_corrupt_media_are_rejected(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    mismatch_service, _owner, mismatch_receiver = make_service(
        tmp_path / "mismatch",
        analysis_id_generator=FixedIdGenerator("mime-mismatch"),
    )
    mismatch = mismatch_service.process(
        BytesIO(media_files["png"].read_bytes()),
        original_name="sample.png",
        declared_content_type="image/jpeg",
        source=source_context(),
    )
    corrupt_service, _owner, corrupt_receiver = make_service(
        tmp_path / "corrupt",
        analysis_id_generator=FixedIdGenerator("corrupt-media"),
    )
    corrupt = corrupt_service.process(
        BytesIO(media_files["png"].read_bytes()[:40]),
        original_name="sample.png",
        declared_content_type=None,
        source=source_context(),
    )

    assert isinstance(mismatch, Stage3Terminal)
    assert mismatch.status is AnalysisStatus.REJECTED
    assert mismatch.errors[0].code == "file_signature_mismatch"
    assert isinstance(corrupt, Stage3Terminal)
    assert corrupt.status is AnalysisStatus.REJECTED
    assert corrupt.errors[0].code == "unsafe_or_unreadable_file"
    assert mismatch_receiver.calls == corrupt_receiver.calls == 0


def test_per_media_limit_rejection_is_terminal_and_cleaned(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    service, _owner, receiver = make_service(
        tmp_path,
        image_limit=1,
        video_limit=2,
    )
    payload = media_files["png"].read_bytes() + b"x" * (1024 * 1024)

    outcome = service.process(
        BytesIO(payload),
        original_name="large.png",
        declared_content_type=None,
        source=source_context(),
    )

    assert isinstance(outcome, Stage3Terminal)
    assert outcome.status is AnalysisStatus.REJECTED
    assert outcome.validation is not None
    assert outcome.errors[0].code == "file_too_large"
    assert receiver.calls == 0
    assert outcome.cleanup is not None
    assert outcome.cleanup.status is CleanupStatus.COMPLETED


def test_pre_detection_hard_limit_has_no_synthetic_validation_and_cleans_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, owner, receiver = make_service(
        tmp_path,
        image_limit=1,
        audio_limit=1,
        video_limit=1,
    )
    cleanup_calls = 0
    real_cleanup = owner.cleanup

    def tracking_cleanup(owned_source) -> None:
        nonlocal cleanup_calls
        cleanup_calls += 1
        real_cleanup(owned_source)

    monkeypatch.setattr(owner, "cleanup", tracking_cleanup)
    payload = b"x" * (1024 * 1024 + 1)

    outcome = service.process(
        BytesIO(payload),
        original_name="oversized.mp4",
        declared_content_type=None,
        source=source_context(),
    )

    assert isinstance(outcome, Stage3Terminal)
    assert outcome.status is AnalysisStatus.REJECTED
    assert outcome.input_file is None
    assert outcome.validation is None
    assert outcome.validated_file is None
    assert outcome.errors[0].code == "file_too_large"
    assert outcome.errors[0].safe_details["observed_size_bytes"] == len(payload)
    assert cleanup_calls == 1
    assert receiver.calls == 0
    assert_no_analysis_outputs(outcome)


def test_workspace_failure_after_registration_has_no_cleanup_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _owner, receiver = make_service(tmp_path)

    def fail_mkdir(
        self: Path,
        mode: int = 0o777,
        *,
        parents: bool = False,
        exist_ok: bool = False,
    ) -> NoReturn:
        raise OSError("PRIVATE WORKSPACE FAILURE")

    monkeypatch.setattr(Path, "mkdir", fail_mkdir)

    outcome = service.process(
        BytesIO(b"content"),
        original_name="sample.png",
        declared_content_type=None,
        source=source_context(),
    )

    assert isinstance(outcome, Stage3Terminal)
    assert outcome.analysis_id == "integrated-stage3"
    assert outcome.status is AnalysisStatus.FAILED
    assert outcome.cleanup is None
    assert outcome.validation is None
    assert outcome.errors[0].code == "internal_error"
    assert receiver.calls == 0


def test_stream_system_failure_is_failed_and_cleanup_is_not_duplicated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, owner, receiver = make_service(tmp_path)
    cleanup_calls = 0
    real_cleanup = owner.cleanup

    def tracking_cleanup(owned_source) -> None:
        nonlocal cleanup_calls
        cleanup_calls += 1
        real_cleanup(owned_source)

    monkeypatch.setattr(owner, "cleanup", tracking_cleanup)

    outcome = service.process(
        PartialThenFailStream(),
        original_name="PRIVATE-NAME.png",
        declared_content_type=None,
        source=source_context(),
    )

    assert isinstance(outcome, Stage3Terminal)
    assert outcome.status is AnalysisStatus.FAILED
    assert outcome.validation is None
    assert outcome.cleanup is not None
    assert outcome.cleanup.status is CleanupStatus.COMPLETED
    assert outcome.errors[0].code == "internal_error"
    assert cleanup_calls == 1
    assert receiver.calls == 0
    assert "PRIVATE" not in outcome.errors[0].message


def test_output_write_failure_is_failed_and_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _owner, _receiver = make_service(tmp_path)

    def fail_write(_descriptor: int, _data: bytes | memoryview) -> NoReturn:
        raise OSError("PRIVATE WRITE FAILURE")

    monkeypatch.setattr(temporary_input_module.os, "write", fail_write)

    outcome = service.process(
        BytesIO(b"content"),
        original_name="sample.png",
        declared_content_type=None,
        source=source_context(),
    )

    assert isinstance(outcome, Stage3Terminal)
    assert outcome.status is AnalysisStatus.FAILED
    assert outcome.cleanup is not None
    assert outcome.cleanup.status is CleanupStatus.COMPLETED
    assert outcome.errors[0].message == "Внутренняя ошибка не позволила завершить приём файла."


def test_validation_system_failure_is_failed_and_cleans_owned_source(tmp_path: Path) -> None:
    class FailingValidator:
        def validate(self, _controlled) -> NoReturn:
            raise ValidationSystemError("PRIVATE VALIDATION PHASE")

    service, _owner, receiver = make_service(tmp_path, validator=FailingValidator())

    outcome = service.process(
        BytesIO(b"content"),
        original_name="sample.png",
        declared_content_type=None,
        source=source_context(),
    )

    assert isinstance(outcome, Stage3Terminal)
    assert outcome.status is AnalysisStatus.FAILED
    assert outcome.input_file is not None
    assert outcome.validation is None
    assert outcome.cleanup is not None
    assert outcome.cleanup.status is CleanupStatus.COMPLETED
    assert receiver.calls == 0


def test_handoff_failure_preserves_successful_validation_and_cleans_moved_source(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    receiver = RecordingReceiver(fail=True)
    service, _owner, _receiver = make_service(tmp_path, receiver=receiver)

    outcome = service.process(
        BytesIO(media_files["png"].read_bytes()),
        original_name="sample.png",
        declared_content_type=None,
        source=source_context(),
    )

    assert isinstance(outcome, Stage3Terminal)
    assert outcome.status is AnalysisStatus.FAILED
    assert outcome.validation is not None
    assert outcome.validation.accepted
    assert outcome.validated_file is outcome.validation.validated_file
    assert outcome.cleanup is not None
    assert outcome.cleanup.status is CleanupStatus.COMPLETED
    assert outcome.errors[0].code == "internal_error"
    assert receiver.accepted is not None
    assert receiver.accepted.controlled_source.is_released
    assert not (tmp_path / "PRIVATE-TEMP" / outcome.analysis_id).exists()
    assert_no_analysis_outputs(outcome)


def test_ownership_transfer_failure_is_failed_and_cleans_original_source(
    tmp_path: Path,
    media_files: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, owner, receiver = make_service(tmp_path)

    def fail_transfer(_owned_source) -> NoReturn:
        raise IntakeSystemError("ownership")

    monkeypatch.setattr(owner, "transfer", fail_transfer)

    outcome = service.process(
        BytesIO(media_files["png"].read_bytes()),
        original_name="sample.png",
        declared_content_type=None,
        source=source_context(),
    )

    assert isinstance(outcome, Stage3Terminal)
    assert outcome.status is AnalysisStatus.FAILED
    assert outcome.validation is not None and outcome.validation.accepted
    assert outcome.cleanup is not None
    assert outcome.cleanup.status is CleanupStatus.COMPLETED
    assert outcome.errors[0].code == "internal_error"
    assert receiver.calls == 0
    assert not (tmp_path / "PRIVATE-TEMP" / outcome.analysis_id).exists()


@pytest.mark.parametrize("failure", ["generator", "invalid"])
def test_pre_registration_failure_is_safe_typed_exception(
    tmp_path: Path,
    failure: str,
) -> None:
    generator = FailingIdGenerator() if failure == "generator" else FixedIdGenerator("../PRIVATE")
    service, _owner, receiver = make_service(tmp_path, analysis_id_generator=generator)

    with pytest.raises(PreRegistrationError) as error_info:
        service.process(
            BytesIO(b"content"),
            original_name="sample.png",
            declared_content_type=None,
            source=source_context(),
        )

    assert str(error_info.value) == "Stage 3 registration failed."
    assert "PRIVATE" not in str(error_info.value)
    assert receiver.calls == 0
    assert not (tmp_path / "PRIVATE-TEMP").exists()


def test_rejection_cleanup_failure_remains_rejected_and_preserves_both_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _owner, _receiver = make_service(tmp_path)

    def fail_unlink(self: Path, *, missing_ok: bool = False) -> NoReturn:
        raise OSError(f"PRIVATE CLEANUP FAILURE {self} {missing_ok}")

    monkeypatch.setattr(Path, "unlink", fail_unlink)

    outcome = service.process(
        BytesIO(b""),
        original_name="empty.png",
        declared_content_type=None,
        source=source_context(),
    )

    assert isinstance(outcome, Stage3Terminal)
    assert outcome.status is AnalysisStatus.REJECTED
    assert outcome.errors[0].code == "file_empty"
    assert outcome.cleanup is not None
    assert outcome.cleanup.status is CleanupStatus.FAILED
    assert outcome.cleanup.errors[0].code == "cleanup_failed"
    assert not outcome.cleanup.original_file_deleted


def test_system_cleanup_failure_remains_failed_and_preserves_both_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _owner, _receiver = make_service(tmp_path)

    def fail_unlink(self: Path, *, missing_ok: bool = False) -> NoReturn:
        raise OSError(f"PRIVATE CLEANUP FAILURE {self} {missing_ok}")

    monkeypatch.setattr(Path, "unlink", fail_unlink)

    outcome = service.process(
        PartialThenFailStream(),
        original_name="sample.png",
        declared_content_type=None,
        source=source_context(),
    )

    assert isinstance(outcome, Stage3Terminal)
    assert outcome.status is AnalysisStatus.FAILED
    assert outcome.errors[0].code == "internal_error"
    assert outcome.cleanup is not None
    assert outcome.cleanup.status is CleanupStatus.FAILED
    assert outcome.cleanup.errors[0].code == "cleanup_failed"


def test_handoff_cleanup_failure_preserves_validation_primary_and_cleanup_error(
    tmp_path: Path,
    media_files: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receiver = RecordingReceiver(fail=True)
    service, _owner, _receiver = make_service(tmp_path, receiver=receiver)

    def fail_unlink(self: Path, *, missing_ok: bool = False) -> NoReturn:
        raise OSError(f"PRIVATE CLEANUP FAILURE {self} {missing_ok}")

    monkeypatch.setattr(Path, "unlink", fail_unlink)

    outcome = service.process(
        BytesIO(media_files["png"].read_bytes()),
        original_name="sample.png",
        declared_content_type=None,
        source=source_context(),
    )

    assert isinstance(outcome, Stage3Terminal)
    assert outcome.status is AnalysisStatus.FAILED
    assert outcome.validation is not None and outcome.validation.accepted
    assert outcome.errors[0].code == "internal_error"
    assert outcome.cleanup is not None
    assert outcome.cleanup.status is CleanupStatus.FAILED
    assert outcome.cleanup.errors[0].code == "cleanup_failed"
    assert receiver.accepted is not None
    assert not receiver.accepted.controlled_source.is_released


def test_partial_cleanup_reports_factual_progress(tmp_path: Path) -> None:
    service, _owner, _receiver = make_service(tmp_path)
    workspace = tmp_path / "PRIVATE-TEMP" / "integrated-stage3"

    class ForeignCreatingValidator:
        def validate(self, _controlled) -> NoReturn:
            (workspace / "foreign.txt").write_text("preserve", encoding="utf-8")
            raise ValidationSystemError("PRIVATE")

    service, _owner, _receiver = make_service(tmp_path, validator=ForeignCreatingValidator())

    outcome = service.process(
        BytesIO(b"content"),
        original_name="sample.png",
        declared_content_type=None,
        source=source_context(),
    )

    assert isinstance(outcome, Stage3Terminal)
    assert outcome.cleanup is not None
    assert outcome.cleanup.status is CleanupStatus.PARTIAL
    assert outcome.cleanup.original_file_deleted
    assert not outcome.cleanup.intermediate_files_deleted
    assert (workspace / "foreign.txt").exists()


def test_non_business_termination_is_reraised_after_single_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class TerminatingValidator:
        def validate(self, _controlled) -> NoReturn:
            raise KeyboardInterrupt

    service, owner, _receiver = make_service(tmp_path, validator=TerminatingValidator())
    cleanup_calls = 0
    real_cleanup = owner.cleanup

    def tracking_cleanup(owned_source) -> None:
        nonlocal cleanup_calls
        cleanup_calls += 1
        real_cleanup(owned_source)

    monkeypatch.setattr(owner, "cleanup", tracking_cleanup)

    with pytest.raises(KeyboardInterrupt):
        service.process(
            BytesIO(b"content"),
            original_name="sample.png",
            declared_content_type=None,
            source=source_context(),
        )

    assert cleanup_calls == 1
    assert not (tmp_path / "PRIVATE-TEMP" / "integrated-stage3").exists()


def test_safe_outcomes_do_not_leak_internal_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = "PRIVATE INTERNAL PATH OR TRACEBACK"
    service, _owner, _receiver = make_service(tmp_path)

    def fail_open(_path: os.PathLike[str], _flags: int, _mode: int) -> NoReturn:
        raise OSError(sentinel)

    monkeypatch.setattr(temporary_input_module.os, "open", fail_open)

    outcome = service.process(
        BytesIO(b"content"),
        original_name="PRIVATE-NAME.png",
        declared_content_type=None,
        source=source_context(),
    )

    assert isinstance(outcome, Stage3Terminal)
    rendered = repr(outcome.errors) + repr(outcome.cleanup)
    assert sentinel not in rendered
    assert str(tmp_path) not in rendered
    assert "PRIVATE-NAME" not in rendered
