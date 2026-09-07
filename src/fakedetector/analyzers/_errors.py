"""Safe internal failures raised by the Stage 5 analyzer framework."""

from __future__ import annotations

from fakedetector.core._cleanup_safety import _CleanupSafetyBarrier


class AnalyzerConfigurationError(ValueError):
    """Reject invalid analyzer registration or configuration without raw values."""

    def __init__(self, phase: str) -> None:
        self.phase = phase
        super().__init__("Analyzer configuration is invalid.")


class AnalyzerInfrastructureError(RuntimeError):
    """Report a fatal orchestration failure without exception or path details."""

    def __init__(
        self,
        phase: str,
        *,
        _cleanup_safety_barrier: _CleanupSafetyBarrier | None = None,
    ) -> None:
        if (phase == "worker_reap") != (_cleanup_safety_barrier is not None):
            raise ValueError("worker reap safety barrier does not match analyzer phase")
        self.phase = phase
        self._cleanup_safety_barrier = _cleanup_safety_barrier
        super().__init__("Analyzer orchestration failed safely.")


class _AnalyzerInputReadError(RuntimeError):
    """Keep worker-local input failures independent of physical path text."""

    def __init__(self) -> None:
        super().__init__("Analyzer input could not be read.")
