"""Private immutable identity for one fully validated application config snapshot."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from fakedetector.config.models import AppConfig


@dataclass(frozen=True, slots=True)
class _ConfigSnapshot:
    """Canonical immutable bytes and their full SHA-256 identity."""

    canonical_json: bytes
    snapshot_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.canonical_json, bytes):
            raise TypeError("canonical config JSON must be immutable bytes")
        expected_id = hashlib.sha256(self.canonical_json).hexdigest()
        if self.snapshot_id != expected_id:
            raise ValueError("config snapshot identity does not match its canonical JSON")

    @classmethod
    def capture(cls, config: AppConfig) -> _ConfigSnapshot:
        """Revalidate current config content before producing canonical bytes."""
        if not isinstance(config, AppConfig):
            raise TypeError("config snapshot requires AppConfig")
        current_data = config.model_dump(mode="python", round_trip=True, warnings="error")
        validated = AppConfig.model_validate(current_data)
        canonical_json = json.dumps(
            validated.model_dump(mode="json", warnings="error"),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return cls(
            canonical_json=canonical_json,
            snapshot_id=hashlib.sha256(canonical_json).hexdigest(),
        )

    def materialize(self) -> AppConfig:
        """Return a new validated mutable model detached from the captured source."""
        return AppConfig.model_validate_json(self.canonical_json)
