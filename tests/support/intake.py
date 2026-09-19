"""Fresh configuration builders for intake and primary validation tests."""

from pathlib import Path

from fakedetector.config.models import AppConfig


def make_config(
    root: Path,
    *,
    image_limit: int = 20,
    audio_limit: int = 50,
    video_limit: int = 200,
) -> AppConfig:
    return AppConfig.model_validate(
        {
            "schema_version": "1.0",
            "server": {},
            "access_channels": {},
            "limits": {
                "max_file_size_mb": {
                    "image": image_limit,
                    "audio": audio_limit,
                    "video": video_limit,
                }
            },
            "allowed_formats": {},
            "validation": {},
            "temporary_storage": {"root_path": str(root)},
            "preprocessing": {},
            "analyzers": {},
            "risk_assessment": {},
            "result": {},
            "error_handling": {},
            "logging": {},
            "external_systems": {},
        }
    )
