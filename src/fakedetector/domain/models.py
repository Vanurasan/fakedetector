"""Canonical Pydantic models for the FakeDetector domain."""

from pydantic import BaseModel, ConfigDict

from fakedetector.domain.enums import SourceChannel


class SourceContext(BaseModel):
    """Context describing how media entered the FakeDetector core."""

    model_config = ConfigDict(extra="forbid")

    channel: SourceChannel
    connector: str | None = None
    external_system: str | None = None
    external_reference: str | None = None
