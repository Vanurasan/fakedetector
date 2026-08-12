"""Core dependency contracts and standard implementations."""

from fakedetector.core.clock import Clock, UtcClock
from fakedetector.core.identity import AnalysisIdGenerator, Uuid4AnalysisIdGenerator

__all__ = [
    "AnalysisIdGenerator",
    "Clock",
    "UtcClock",
    "Uuid4AnalysisIdGenerator",
]
