"""Narrow persistence-success test double for pre-Stage 8 lifecycle tests."""

from collections.abc import Callable
from datetime import datetime
from threading import Lock

from fakedetector.lifecycle.models import TerminalTaskFacts


class SuccessfulAcceptedResultFinalizer:
    """Acknowledge the persistence port after invoking its lifecycle boundary."""

    def __init__(self) -> None:
        self.facts: TerminalTaskFacts | None = None
        self.finished_at: datetime | None = None
        self.facts_by_analysis_id: dict[str, TerminalTaskFacts] = {}
        self.finished_at_by_analysis_id: dict[str, datetime] = {}
        self._lock = Lock()

    def finalize_accepted(
        self,
        facts: TerminalTaskFacts,
        *,
        finished_at: datetime,
        before_save: Callable[[], None],
    ) -> object:
        with self._lock:
            self.facts = facts
            self.finished_at = finished_at
            self.facts_by_analysis_id[facts.analysis_id] = facts
            self.finished_at_by_analysis_id[facts.analysis_id] = finished_at
        before_save()
        return object()
