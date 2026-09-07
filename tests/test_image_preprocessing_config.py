"""Mandatory Stage 5 image normalization configuration validation."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError as PydanticValidationError

from fakedetector.config.loader import ConfigurationError, load_config
from fakedetector.config.models import ImagePreprocessingConfig


@pytest.mark.parametrize("settings", [{}, {"normalize_for_analysis": True}])
def test_image_normalization_is_mandatory_with_default_or_explicit_true(
    settings: dict[str, bool],
) -> None:
    assert ImagePreprocessingConfig.model_validate(settings).normalize_for_analysis is True


def test_image_normalization_false_is_rejected_by_model() -> None:
    with pytest.raises(PydanticValidationError, match="image normalization must be enabled"):
        ImagePreprocessingConfig(normalize_for_analysis=False)


@pytest.mark.parametrize("source", ["yaml", "env"])
def test_disabling_image_normalization_is_a_controlled_configuration_failure(
    tmp_path: Path, source: str
) -> None:
    raw = yaml.safe_load(Path("config/config.example.yaml").read_text(encoding="utf-8"))
    env = {}
    if source == "yaml":
        raw["preprocessing"]["image"]["normalize_for_analysis"] = False
    else:
        env["FAKEDETECTOR_PREPROCESSING__IMAGE__NORMALIZE_FOR_ANALYSIS"] = "false"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(raw), encoding="utf-8")

    with pytest.raises(ConfigurationError, match="validation failed"):
        load_config(config_path, env=env)
