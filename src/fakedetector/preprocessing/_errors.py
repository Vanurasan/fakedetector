"""Safe internal failures for Stage 5 preprocessing."""

from __future__ import annotations

from typing import Literal

from fakedetector.core._cleanup_safety import _CleanupSafetyBarrier

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

    def __init__(
        self,
        kind: PreprocessingFailureKind,
        phase: str,
        *,
        _cleanup_safety_barrier: _CleanupSafetyBarrier | None = None,
    ) -> None:
        if _cleanup_safety_barrier is not None and kind != "infrastructure":
            raise ValueError("cleanup safety barrier requires infrastructure failure")
        super().__init__("Media preprocessing failed.")
        self.kind = kind
        self.phase = phase
        self._cleanup_safety_barrier = _cleanup_safety_barrier
