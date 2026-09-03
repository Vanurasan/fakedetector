"""Safe internal failures for Stage 5 preprocessing."""

from __future__ import annotations

from typing import Literal

PreprocessingFailureKind = Literal[
    "source_read",
    "decode",
    "media_tool",
    "artifact_write",
    "invariant",
    "infrastructure",
]


class PreprocessingError(Exception):
    """Describe one controlled internal failure without leaking media locations."""

    def __init__(self, kind: PreprocessingFailureKind, phase: str) -> None:
        super().__init__("Media preprocessing failed.")
        self.kind = kind
        self.phase = phase
