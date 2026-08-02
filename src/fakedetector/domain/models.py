"""Canonical Pydantic models for the FakeDetector domain."""

from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator

from fakedetector.domain.enums import SourceChannel


class SourceContext(BaseModel):
    """Context describing how media entered the FakeDetector core."""

    model_config = ConfigDict(extra="forbid")

    channel: SourceChannel
    connector: str | None = None
    external_system: str | None = None
    external_reference: str | None = None


class InputFileDescriptor(BaseModel):
    """Metadata supplied when an input file is received."""

    model_config = ConfigDict(extra="forbid")

    original_name: str
    declared_content_type: str | None
    size_bytes: int
    received_at: datetime

    @field_validator("received_at")
    @classmethod
    def validate_received_at_is_utc(cls, value: datetime) -> datetime:
        """Require an aware UTC value without converting another timezone."""
        if value.utcoffset() != timedelta(0):
            raise ValueError("received_at must be a timezone-aware UTC datetime")
        return value

    @field_serializer("received_at", when_used="json")
    def serialize_received_at(self, value: datetime) -> str:
        """Serialize the validated UTC timestamp with the canonical Z suffix."""
        return value.isoformat().replace("+00:00", "Z")
