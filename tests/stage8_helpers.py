"""Shared deterministic helpers for Stage 8 Macro 2 transport tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fakedetector.application import (
    AnalysisStatusView,
    AnalysisSubmission,
)
from fakedetector.config.models import AppConfig
from fakedetector.domain import (
    AnalysisResult,
    AnalysisStatus,
    ErrorDetail,
    ProcessingStage,
    SourceContext,
)
from fakedetector.intake import ReadableBinaryStream

NOW = datetime(2026, 9, 11, 4, 0, tzinfo=UTC)
FINISHED = datetime(2026, 9, 11, 4, 1, tzinfo=UTC)


def make_config(
    root: Path,
    *,
    api_enabled: bool = True,
    api_auth: bool = True,
    webui_enabled: bool = True,
    webui_auth: bool = True,
) -> AppConfig:
    return AppConfig.model_validate(
        {
            "schema_version": "1.0",
            "server": {},
            "access_channels": {
                "api": {
                    "enabled": api_enabled,
                    "require_token": api_auth,
                    "token_env_var": "MEDIA_ANALYZER_API_TOKEN",
                },
                "webui": {
                    "enabled": webui_enabled,
                    "require_authentication": webui_auth,
                    "credentials_env_var": "MEDIA_ANALYZER_WEBUI_CREDENTIALS",
                },
            },
            "limits": {},
            "allowed_formats": {},
            "validation": {},
            "temporary_storage": {"root_path": str(root / "temp")},
            "preprocessing": {},
            "analyzers": {},
            "risk_assessment": {},
            "result": {"directory": str(root / "results")},
            "error_handling": {},
            "logging": {"jsonl_path": str(root / "logs" / "application.jsonl")},
            "external_systems": {},
        }
    )


def make_error(
    code: str = "internal_error",
    category: str = "internal",
    *,
    message: str = "Безопасное сообщение.",
) -> ErrorDetail:
    return ErrorDetail.model_validate(
        {
            "code": code,
            "category": category,
            "message": message,
            "retryable": False,
        }
    )


def make_status(
    analysis_id: str = "analysis-001",
    *,
    status: AnalysisStatus = AnalysisStatus.RUNNING,
    stage: ProcessingStage = ProcessingStage.ANALYSIS,
    result_available: bool = False,
    errors: tuple[ErrorDetail, ...] = (),
) -> AnalysisStatusView:
    return AnalysisStatusView(
        analysis_id=analysis_id,
        status=status,
        stage=stage,
        created_at=NOW,
        queued_at=NOW,
        started_at=NOW,
        finished_at=FINISHED if stage is ProcessingStage.FINISHED else None,
        result_available=result_available,
        errors=errors,
    )


def make_completed_result(
    analysis_id: str = "analysis-001",
    *,
    channel: str = "api",
) -> AnalysisResult:
    return AnalysisResult.model_validate(
        {
            "schema_version": "1.0",
            "analysis_id": analysis_id,
            "created_at": NOW,
            "updated_at": FINISHED,
            "status": "completed",
            "stage": "finished",
            "source": {"channel": channel},
            "file": {
                "original_name": "sample.png",
                "extension": "png",
                "declared_mime_type": "image/png",
                "detected_mime_type": "image/png",
                "media_type": "image",
                "size_bytes": 128,
                "sha256": "test-digest",
                "signature_match": True,
                "safe_read": True,
                "technical_parameters": {
                    "width": 16,
                    "height": 12,
                    "format": "PNG",
                    "color_mode": "RGB",
                    "frame_count": None,
                    "has_metadata": False,
                },
            },
            "processing": {
                "queued_at": NOW,
                "started_at": NOW,
                "finished_at": FINISHED,
                "duration_ms": 60_000,
                "config_snapshot_id": "test-config",
                "application_version": "0.1.0",
            },
            "analyzers": [],
            "findings": [],
            "completeness": {
                "status": "complete",
                "planned_analyzers": 0,
                "applicable_analyzers": 0,
                "completed_analyzers": 0,
                "failed_analyzers": 0,
                "timed_out_analyzers": 0,
                "skipped_analyzers": 0,
                "not_applicable_analyzers": 0,
                "coverage_ratio": 1.0,
                "missing_capabilities": [],
                "explanation": "Все запланированные проверки выполнены.",
            },
            "risk_assessment": {
                "model_id": "score_model_v1",
                "model_version": "0.1.0",
                "score": 0,
                "score_based_level": "low",
                "critical_override_applied": False,
                "critical_finding_ids": [],
                "final_level": "low",
                "probability": None,
                "probability_method": None,
                "summary": "Значимые признаки не выявлены.",
                "explanation": "Фактическая оценка тестового результата.",
                "limitations": ["Тестовое ограничение."],
            },
            "recommendation": {
                "primary_action": "no_additional_action",
                "additional_actions": [],
                "text": "Учитывайте ограничения автоматизированной оценки.",
                "requires_manual_review": False,
            },
            "cleanup": {
                "status": "completed",
                "original_file_deleted": True,
                "intermediate_files_deleted": True,
                "quarantine_used": False,
                "finished_at": FINISHED,
                "errors": [],
            },
            "warnings": [],
            "errors": [],
        }
    )


def make_rejected_result(
    analysis_id: str = "analysis-rejected",
    *,
    code: str = "unsupported_extension",
    category: str = "unsupported_media",
    status: AnalysisStatus = AnalysisStatus.REJECTED,
) -> AnalysisResult:
    return AnalysisResult.model_validate(
        {
            "schema_version": "1.0",
            "analysis_id": analysis_id,
            "created_at": NOW,
            "updated_at": FINISHED,
            "status": status,
            "stage": "finished",
            "source": {"channel": "api"},
            "file": None,
            "processing": {
                "queued_at": None,
                "started_at": None,
                "finished_at": FINISHED,
                "duration_ms": None,
                "config_snapshot_id": "test-config",
                "application_version": "0.1.0",
            },
            "analyzers": [],
            "findings": [],
            "completeness": {
                "status": "not_assessed",
                "planned_analyzers": None,
                "applicable_analyzers": None,
                "completed_analyzers": None,
                "failed_analyzers": None,
                "timed_out_analyzers": None,
                "skipped_analyzers": None,
                "not_applicable_analyzers": None,
                "coverage_ratio": None,
                "missing_capabilities": [],
                "explanation": "Полнота анализа не оценивалась.",
            },
            "risk_assessment": None,
            "recommendation": None,
            "cleanup": None,
            "warnings": [],
            "errors": [make_error(code, category)],
        }
    )


class StubApplicationService:
    """Controllable shared service double for HTTP adapters."""

    def __init__(self) -> None:
        self.submission = AnalysisSubmission(
            analysis_id="analysis-001",
            status=AnalysisStatus.RUNNING,
            stage=ProcessingStage.ANALYSIS,
            terminal_result=None,
        )
        self.status = make_status()
        self.result = make_completed_result()
        self.submit_error: Exception | None = None
        self.status_error: Exception | None = None
        self.result_error: Exception | None = None
        self.sources: list[SourceContext] = []
        self.original_names: list[str] = []
        self.declared_content_types: list[str | None] = []
        self.payloads: list[bytes] = []

    def submit(
        self,
        stream: ReadableBinaryStream,
        *,
        original_name: str,
        declared_content_type: str | None,
        source: SourceContext,
    ) -> AnalysisSubmission:
        self.payloads.append(stream.read(64 * 1024))
        self.original_names.append(original_name)
        self.declared_content_types.append(declared_content_type)
        self.sources.append(source)
        if self.submit_error is not None:
            raise self.submit_error
        return self.submission

    def get_status(self, analysis_id: str) -> AnalysisStatusView:
        del analysis_id
        if self.status_error is not None:
            raise self.status_error
        return self.status

    def get_result(self, analysis_id: str) -> AnalysisResult:
        del analysis_id
        if self.result_error is not None:
            raise self.result_error
        return self.result
