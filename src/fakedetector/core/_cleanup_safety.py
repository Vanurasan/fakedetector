"""Private cleanup-safety contract for unresolved process ownership."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class _CleanupSafetyBarrier(Protocol):
    """Boundedly confirm that physical task cleanup can safely begin."""

    def try_confirm_safe(self) -> bool:
        """Return whether every retained reader/process is confirmed stopped."""
        ...


class _CleanupSafetyInterruption(BaseException):
    """Carry an interruption and its unresolved R1 barrier to the lifecycle owner."""

    def __init__(
        self,
        interruption: BaseException,
        barrier: _CleanupSafetyBarrier,
    ) -> None:
        super().__init__("Process interruption requires cleanup safety confirmation.")
        self.interruption = interruption
        self._cleanup_safety_barrier = barrier
