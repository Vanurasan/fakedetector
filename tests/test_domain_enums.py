"""Contract tests for FakeDetector domain enumerations."""

from __future__ import annotations

import json
from enum import StrEnum

import pytest

import fakedetector.domain as domain
from fakedetector.domain import (
    AnalysisStatus,
    AnalyzerStatus,
    CleanupStatus,
    CompletenessStatus,
    FindingSeverity,
    MediaType,
    ProcessingStage,
    RiskLevel,
    SourceChannel,
)

EXPECTED_ENUMS: dict[type[StrEnum], dict[str, str]] = {
    MediaType: {
        "IMAGE": "image",
        "AUDIO": "audio",
        "VIDEO": "video",
    },
    SourceChannel: {
        "WEBUI": "webui",
        "API": "api",
    },
    AnalysisStatus: {
        "QUEUED": "queued",
        "RUNNING": "running",
        "COMPLETED": "completed",
        "PARTIAL": "partial",
        "REJECTED": "rejected",
        "FAILED": "failed",
    },
    ProcessingStage: {
        "REGISTERED": "registered",
        "VALIDATION": "validation",
        "ROUTING": "routing",
        "QUEUED": "queued",
        "PREPROCESSING": "preprocessing",
        "ANALYSIS": "analysis",
        "FINDING_FORMATION": "finding_formation",
        "RISK_ASSESSMENT": "risk_assessment",
        "RESULT_FORMATION": "result_formation",
        "CLEANUP": "cleanup",
        "PERSISTENCE": "persistence",
        "FINISHED": "finished",
    },
    AnalyzerStatus: {
        "COMPLETED": "completed",
        "SKIPPED": "skipped",
        "NOT_APPLICABLE": "not_applicable",
        "ERROR": "error",
        "TIMEOUT": "timeout",
    },
    FindingSeverity: {
        "WEAK": "weak",
        "SIGNIFICANT": "significant",
        "CRITICAL": "critical",
    },
    RiskLevel: {
        "LOW": "low",
        "MEDIUM": "medium",
        "HIGH": "high",
    },
    CompletenessStatus: {
        "COMPLETE": "complete",
        "PARTIAL": "partial",
        "INSUFFICIENT": "insufficient",
        "NOT_ASSESSED": "not_assessed",
    },
    CleanupStatus: {
        "NOT_STARTED": "not_started",
        "COMPLETED": "completed",
        "PARTIAL": "partial",
        "FAILED": "failed",
    },
}

EXPECTED_EXPORTS = [
    "AnalysisStatus",
    "AnalyzerStatus",
    "CleanupStatus",
    "CompletenessStatus",
    "FindingSeverity",
    "MediaType",
    "ProcessingStage",
    "RiskLevel",
    "SourceChannel",
]


@pytest.mark.parametrize(("enum_type", "expected_members"), EXPECTED_ENUMS.items())
def test_enum_names_and_values_match_contract(
    enum_type: type[StrEnum],
    expected_members: dict[str, str],
) -> None:
    assert issubclass(enum_type, StrEnum)
    assert enum_type.__members__ == {
        name: enum_type(value) for name, value in expected_members.items()
    }
    assert {member.name: member.value for member in enum_type} == expected_members


@pytest.mark.parametrize(("enum_type", "expected_members"), EXPECTED_ENUMS.items())
def test_enum_accepts_known_and_rejects_unknown_values(
    enum_type: type[StrEnum],
    expected_members: dict[str, str],
) -> None:
    first_value = next(iter(expected_members.values()))

    assert enum_type(first_value).value == first_value
    with pytest.raises(ValueError):
        enum_type("unknown")


def test_domain_exports_exactly_the_contract_enums() -> None:
    assert domain.__all__ == EXPECTED_EXPORTS
    assert {name: getattr(domain, name) for name in domain.__all__} == {
        enum_type.__name__: enum_type for enum_type in EXPECTED_ENUMS
    }


@pytest.mark.parametrize("enum_type", EXPECTED_ENUMS)
def test_enum_json_round_trip(enum_type: type[StrEnum]) -> None:
    for member in enum_type:
        decoded_value = json.loads(json.dumps(member))

        assert decoded_value == member.value
        assert enum_type(decoded_value) is member
