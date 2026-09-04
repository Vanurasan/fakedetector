"""Demand declarations shared by analyzer planning and preprocessing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PreprocessingRequirements:
    """Representations required by the active analyzer plan."""

    audio_spectrogram: bool = False
    video_audio_track: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.audio_spectrogram, bool) or not isinstance(
            self.video_audio_track, bool
        ):
            raise TypeError("preprocessing requirements must be booleans")
