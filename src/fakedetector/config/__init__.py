"""Configuration package for FakeDetector.

Provides typed YAML configuration loading and validation via Pydantic models.
"""

from fakedetector.config.loader import ConfigurationError, load_config
from fakedetector.config.models import AppConfig

__all__ = ["AppConfig", "ConfigurationError", "load_config"]
