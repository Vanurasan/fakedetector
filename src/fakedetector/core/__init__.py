"""Core dependency contracts and standard implementations."""

from fakedetector.core.clock import (
    AuthoritativeLifecycleClock,
    Clock,
    UtcClock,
)
from fakedetector.core.identity import AnalysisIdGenerator, Uuid4AnalysisIdGenerator

__all__ = [
    "AnalysisIdGenerator",
    "AuthoritativeLifecycleClock",
    "Clock",
    "UtcClock",
    "Uuid4AnalysisIdGenerator",
]
