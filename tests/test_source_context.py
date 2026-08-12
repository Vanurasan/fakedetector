"""Contract tests for the SourceContext domain model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

import fakedetector.domain as domain
from fakedetector.domain import SourceChannel, SourceContext
from fakedetector.domain.models import SourceContext as ModelsSourceContext

EXPECTED_DOMAIN_EXPORTS = [
    "AnalysisStatus",
    "AnalyzerStatus",
    "AudioTechnicalParameters",
    "CleanupStatus",
    "CompletenessStatus",
    "ErrorDetail",
    "FindingSeverity",
    "ImageTechnicalParameters",
    "InputFileDescriptor",
    "MediaType",
    "ProcessingStage",
    "RiskLevel",
    "SourceChannel",
    "SourceContext",
    "ValidatedFileDescriptor",
    "ValidationCheck",
    "ValidationResult",
    "VideoTechnicalParameters",
]


@pytest.mark.parametrize("channel", list(SourceChannel))
def test_source_context_accepts_each_channel(channel: SourceChannel) -> None:
    source = SourceContext(channel=channel)

    assert source.channel is channel


def test_source_context_converts_string_channel_to_enum() -> None:
    source = SourceContext.model_validate({"channel": "api"})

    assert source.channel is SourceChannel.API


def test_source_context_requires_channel() -> None:
    with pytest.raises(ValidationError):
        SourceContext.model_validate({})


def test_source_context_rejects_unknown_channel() -> None:
    with pytest.raises(ValidationError):
        SourceContext.model_validate({"channel": "mail_connector"})


def test_source_context_optional_fields_default_to_none() -> None:
    source = SourceContext(channel=SourceChannel.WEBUI)

    assert source.connector is None
    assert source.external_system is None
    assert source.external_reference is None


def test_source_context_accepts_strings_for_optional_fields() -> None:
    source = SourceContext(
        channel=SourceChannel.API,
        connector="mail_connector",
        external_system="corporate_mail_gateway",
        external_reference="mail-784512",
    )

    assert source.connector == "mail_connector"
    assert source.external_system == "corporate_mail_gateway"
    assert source.external_reference == "mail-784512"


def test_source_context_accepts_explicit_null_for_optional_fields() -> None:
    source = SourceContext.model_validate_json(
        """{
            "channel": "api",
            "connector": null,
            "external_system": null,
            "external_reference": null
        }"""
    )

    assert source.connector is None
    assert source.external_system is None
    assert source.external_reference is None


def test_source_context_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        SourceContext.model_validate({"channel": "webui", "sender_address": "private"})


def test_source_context_model_dump_is_json_compatible() -> None:
    source = SourceContext(
        channel=SourceChannel.API,
        connector="mail_connector",
        external_system="corporate_mail_gateway",
        external_reference="mail-784512",
    )

    assert source.model_dump(mode="json") == {
        "channel": "api",
        "connector": "mail_connector",
        "external_system": "corporate_mail_gateway",
        "external_reference": "mail-784512",
    }


def test_source_context_json_round_trip() -> None:
    source = SourceContext(
        channel=SourceChannel.API,
        connector="mail_connector",
        external_system="corporate_mail_gateway",
        external_reference="mail-784512",
    )

    restored = SourceContext.model_validate_json(source.model_dump_json())

    assert restored == source
    assert restored.channel is SourceChannel.API


def test_source_context_is_available_by_direct_domain_import() -> None:
    assert SourceContext is ModelsSourceContext
    assert domain.SourceContext is ModelsSourceContext


def test_domain_all_has_exact_expected_content() -> None:
    assert domain.__all__ == EXPECTED_DOMAIN_EXPORTS
