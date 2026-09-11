"""Narrow persistence-success test double for pre-Stage 8 lifecycle tests."""

from collections.abc import Callable
from datetime import datetime

from fakedetector.lifecycle.models import TerminalTaskFacts


class SuccessfulAcceptedResultFinalizer:
    """Acknowledge the persistence port after invoking its lifecycle boundary."""

    def finalize_accepted(
        self,
        facts: TerminalTaskFacts,
        *,
        finished_at: datetime,
        before_save: Callable[[], None],
    ) -> object:
        del facts, finished_at
        before_save()
        return object()
