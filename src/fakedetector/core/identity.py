"""Opaque analysis ID generation contracts."""

import uuid
from typing import Protocol, runtime_checkable


@runtime_checkable
class AnalysisIdGenerator(Protocol):
    """Generate opaque identifiers for analysis tasks."""

    def generate(self) -> str:
        """Return a new opaque analysis identifier."""
        ...


class Uuid4AnalysisIdGenerator:
    """Generate lowercase UUID4 hexadecimal identifiers."""

    def generate(self) -> str:
        """Return the 32-character hexadecimal representation of UUID4."""
        return uuid.uuid4().hex
