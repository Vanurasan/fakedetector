"""Contract tests for primary validation result domain models."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

import fakedetector.domain as domain
from fakedetector.domain import (
    ErrorDetail,
    ValidatedFileDescriptor,
    ValidationCheck,
    ValidationResult,
)
from fakedetector.domain.models import ErrorDetail as ModelsErrorDetail
from fakedetector.domain.models import ValidationCheck as ModelsValidationCheck
from fakedetector.domain.models import ValidationResult as ModelsValidationResult

EXPECTED_DOMAIN_EXPORTS = [
    "AnalysisCompleteness",
    "AnalysisResult",
    "AnalysisResultSummary",
    "AnalysisStatus",
    "AnalyzerResult",
    "AnalyzerStatus",
    "AudioTechnicalParameters",
    "BoundingBoxLocalization",
    "CleanupResult",
    "CleanupStatus",
    "CompletenessStatus",
    "ErrorDetail",
    "FileLocalization",
    "Finding",
    "FindingSeverity",
    "FrameIntervalLocalization",
    "ImageTechnicalParameters",
    "InputFileDescriptor",
    "Localization",
    "MediaType",
    "ProcessingStage",
    "Recommendation",
    "RiskAssessment",
    "RiskLevel",
    "SourceChannel",
    "SourceContext",
    "TimeIntervalLocalization",
    "ValidatedFileDescriptor",
    "ValidationCheck",
    "ValidationResult",
    "VideoTechnicalParameters",
]

CANONICAL_ERROR_CATEGORIES = [
    "authentication",
    "authorization",
    "validation",
    "unsupported_media",
    "resource_limit",
    "processing",
    "analyzer",
    "storage",
    "cleanup",
    "configuration",
    "internal",
]

VALIDATION_CHECK_DATA: dict[str, Any] = {
    "code": "file_size_allowed",
    "passed": True,
    "message": "Размер файла соответствует ограничению.",
}

ERROR_DETAIL_DATA: dict[str, Any] = {
    "code": "file_signature_mismatch",
    "category": "validation",
    "message": "Фактический тип файла не соответствует заявленному.",
    "retryable": False,
}

VALIDATED_FILE_DATA: dict[str, Any] = {
    "original_name": "image.jpg",
    "extension": "jpg",
    "declared_mime_type": "image/jpeg",
    "detected_mime_type": "image/jpeg",
    "media_type": "image",
    "size_bytes": 2048,
    "sha256": "not-validated-by-this-contract",
    "signature_match": True,
    "safe_read": True,
    "technical_parameters": {
        "width": 1280,
        "height": 720,
        "format": "JPEG",
        "color_mode": "RGB",
        "has_metadata": False,
    },
}


def validation_result_data() -> dict[str, Any]:
    """Return a complete accepted validation result as nested dictionaries."""
    return {
        "accepted": True,
        "checks": [VALIDATION_CHECK_DATA.copy()],
        "errors": [],
        "validated_file": {
            **VALIDATED_FILE_DATA,
            "technical_parameters": VALIDATED_FILE_DATA["technical_parameters"].copy(),
        },
    }


def rejected_validation_result_data() -> dict[str, Any]:
    """Return a complete rejected validation result as nested dictionaries."""
    return {
        "accepted": False,
        "checks": [VALIDATION_CHECK_DATA.copy()],
        "errors": [ERROR_DETAIL_DATA.copy()],
        "validated_file": None,
    }


def test_validation_check_accepts_all_contract_fields() -> None:
    check = ValidationCheck(**VALIDATION_CHECK_DATA)

    assert check.code == "file_size_allowed"
    assert check.passed is True
    assert check.message == "Размер файла соответствует ограничению."


@pytest.mark.parametrize("missing_field", VALIDATION_CHECK_DATA)
def test_validation_check_requires_each_field(missing_field: str) -> None:
    data = VALIDATION_CHECK_DATA.copy()
    del data[missing_field]

    with pytest.raises(ValidationError):
        ValidationCheck.model_validate(data)


def test_validation_check_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        ValidationCheck.model_validate({**VALIDATION_CHECK_DATA, "duration_ms": 12})


def test_validation_check_json_dump_and_round_trip() -> None:
    check = ValidationCheck(**VALIDATION_CHECK_DATA)

    dumped = check.model_dump(mode="json")
    restored = ValidationCheck.model_validate_json(check.model_dump_json())

    assert json.loads(json.dumps(dumped)) == dumped
    assert restored == check


def test_error_detail_accepts_minimal_contract_fields() -> None:
    error = ErrorDetail(**ERROR_DETAIL_DATA)

    assert error.code == "file_signature_mismatch"
    assert error.category == "validation"
    assert error.message == "Фактический тип файла не соответствует заявленному."
    assert error.retryable is False
    assert error.field is None
    assert error.analyzer_id is None
    assert error.safe_details == {}


@pytest.mark.parametrize("missing_field", ["code", "category", "message", "retryable"])
def test_error_detail_requires_each_main_field(missing_field: str) -> None:
    data = ERROR_DETAIL_DATA.copy()
    del data[missing_field]

    with pytest.raises(ValidationError):
        ErrorDetail.model_validate(data)


def test_error_detail_accepts_explicit_null_optional_fields() -> None:
    error = ErrorDetail(
        **ERROR_DETAIL_DATA,
        field=None,
        analyzer_id=None,
    )

    assert error.field is None
    assert error.analyzer_id is None


def test_error_detail_default_safe_details_are_independent() -> None:
    first_error = ErrorDetail(**ERROR_DETAIL_DATA)
    second_error = ErrorDetail(**ERROR_DETAIL_DATA)

    first_error.safe_details["limit_bytes"] = 1024

    assert first_error.safe_details == {"limit_bytes": 1024}
    assert second_error.safe_details == {}
    assert first_error.safe_details is not second_error.safe_details


@pytest.mark.parametrize("category", CANONICAL_ERROR_CATEGORIES)
def test_error_detail_accepts_each_canonical_category(category: str) -> None:
    error = ErrorDetail.model_validate({**ERROR_DETAIL_DATA, "category": category})

    assert error.category == category


def test_error_detail_rejects_unknown_category() -> None:
    with pytest.raises(ValidationError):
        ErrorDetail.model_validate({**ERROR_DETAIL_DATA, "category": "network"})


def test_error_detail_accepts_stable_code_not_in_current_mvp_table() -> None:
    error = ErrorDetail.model_validate(
        {**ERROR_DETAIL_DATA, "code": "future_stable_validation_code"}
    )

    assert error.code == "future_stable_validation_code"


def test_error_detail_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        ErrorDetail.model_validate({**ERROR_DETAIL_DATA, "stack_trace": "private details"})


def test_error_detail_rejects_non_json_safe_details() -> None:
    with pytest.raises(ValidationError):
        ErrorDetail.model_validate({**ERROR_DETAIL_DATA, "safe_details": {"raw": object()}})


def test_error_detail_json_dump_and_round_trip() -> None:
    error = ErrorDetail(
        **ERROR_DETAIL_DATA,
        field="file",
        analyzer_id=None,
        safe_details={
            "expected": "image/jpeg",
            "limits": {"size_bytes": 10_000, "allowed": True},
            "alternatives": ["image/png", None],
        },
    )

    dumped = error.model_dump(mode="json")
    restored = ErrorDetail.model_validate_json(error.model_dump_json())

    assert json.loads(json.dumps(dumped)) == dumped
    assert restored == error


def test_validation_result_accepts_validated_file_descriptor() -> None:
    descriptor = ValidatedFileDescriptor.model_validate(VALIDATED_FILE_DATA)
    check = ValidationCheck(**VALIDATION_CHECK_DATA)
    result = ValidationResult(
        accepted=True,
        checks=[check],
        errors=[],
        validated_file=descriptor,
    )

    assert result.accepted is True
    assert result.checks == [check]
    assert result.errors == []
    assert result.validated_file is descriptor


def test_validation_result_accepts_valid_rejection() -> None:
    result = ValidationResult(
        accepted=False,
        checks=[ValidationCheck(**VALIDATION_CHECK_DATA)],
        errors=[ErrorDetail(**ERROR_DETAIL_DATA)],
        validated_file=None,
    )

    assert result.validated_file is None


@pytest.mark.parametrize(
    ("accepted", "validated_file", "errors"),
    [
        (True, None, []),
        (True, VALIDATED_FILE_DATA, [ERROR_DETAIL_DATA]),
        (False, None, []),
        (False, VALIDATED_FILE_DATA, [ERROR_DETAIL_DATA]),
    ],
    ids=[
        "success-without-validated-file",
        "success-with-errors",
        "rejection-without-errors",
        "rejection-with-validated-file",
    ],
)
def test_validation_result_rejects_contradictory_outcomes(
    accepted: bool,
    validated_file: dict[str, Any] | None,
    errors: list[dict[str, Any]],
) -> None:
    with pytest.raises(ValidationError):
        ValidationResult.model_validate(
            {
                "accepted": accepted,
                "checks": [VALIDATION_CHECK_DATA.copy()],
                "errors": errors,
                "validated_file": validated_file,
            }
        )


def test_validation_result_validates_nested_dictionaries_as_contract_models() -> None:
    data = rejected_validation_result_data()

    result = ValidationResult.model_validate(data)

    assert isinstance(result.checks[0], ValidationCheck)
    assert isinstance(result.errors[0], ErrorDetail)
    assert result.validated_file is None


@pytest.mark.parametrize("missing_field", ["accepted", "checks", "errors", "validated_file"])
def test_validation_result_requires_each_field(missing_field: str) -> None:
    data = validation_result_data()
    del data[missing_field]

    with pytest.raises(ValidationError):
        ValidationResult.model_validate(data)


def test_validation_result_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        ValidationResult.model_validate({**validation_result_data(), "analysis_id": "private"})


def test_validation_result_checks_have_validation_check_type() -> None:
    result = ValidationResult.model_validate(validation_result_data())

    assert all(isinstance(check, ValidationCheck) for check in result.checks)


def test_validation_result_errors_have_error_detail_type() -> None:
    data = rejected_validation_result_data()

    result = ValidationResult.model_validate(data)

    assert all(isinstance(error, ErrorDetail) for error in result.errors)


def test_validation_result_model_dump_is_json_compatible() -> None:
    data = validation_result_data()
    result = ValidationResult.model_validate(data)

    dumped = result.model_dump(mode="json")

    assert json.loads(json.dumps(dumped)) == dumped
    assert set(dumped) == {"accepted", "checks", "errors", "validated_file"}
    assert dumped["validated_file"]["media_type"] == "image"


def test_validation_result_json_round_trip() -> None:
    data = rejected_validation_result_data()
    result = ValidationResult.model_validate(data)

    restored = ValidationResult.model_validate_json(result.model_dump_json())

    assert restored == result
    assert isinstance(restored.checks[0], ValidationCheck)
    assert isinstance(restored.errors[0], ErrorDetail)
    assert restored.validated_file is None


def test_new_models_are_available_by_direct_domain_import() -> None:
    assert ErrorDetail is ModelsErrorDetail
    assert ValidationCheck is ModelsValidationCheck
    assert ValidationResult is ModelsValidationResult
    assert domain.ErrorDetail is ModelsErrorDetail
    assert domain.ValidationCheck is ModelsValidationCheck
    assert domain.ValidationResult is ModelsValidationResult


def test_domain_all_has_exact_expected_content() -> None:
    assert domain.__all__ == EXPECTED_DOMAIN_EXPORTS
