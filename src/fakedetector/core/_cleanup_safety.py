"""Private cleanup-safety contract for unresolved process ownership."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class _CleanupSafetyBarrier(Protocol):
    """Boundedly confirm that physical task cleanup can safely begin."""

    def try_confirm_safe(self) -> bool:
        """Return whether every retained reader/process is confirmed stopped."""
        ...
