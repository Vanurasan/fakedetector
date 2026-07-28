"""Tests for configuration loading and validation."""

from __future__ import annotations

import tempfile
import traceback
from pathlib import Path

import pytest
from pytest import param

from fakedetector.config.loader import ConfigurationError, load_config
from fakedetector.config.models import AppConfig, LoggingConfig


def test_valid_config_loads() -> None:
    """A minimal valid YAML configuration loads successfully."""
    yaml_content = """\
schema_version: "1.0"
server:
  host: "0.0.0.0"
  port: 9090
access_channels:
  webui:
    enabled: true
    require_authentication: true
  api:
    enabled: true
    require_token: true
    token_env_var: "MEDIA_ANALYZER_API_TOKEN"
limits:
  max_file_size_mb:
    image: 20
    audio: 50
    video: 200
  max_parallel_tasks:
    image: 4
    audio: 2
    video: 1
  processing_timeout_seconds: 600
allowed_formats:
  image:
    extensions: ["jpg", "jpeg", "png", "webp"]
    mime_types: ["image/jpeg", "image/png", "image/webp"]
  audio:
    extensions: ["wav", "mp3", "flac", "m4a"]
    mime_types: ["audio/wav", "audio/mpeg", "audio/flac", "audio/mp4"]
  video:
    extensions: ["mp4", "mov", "avi", "mkv"]
    mime_types: ["video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska"]
validation:
  check_extension: true
  check_mime_type: true
  check_file_signature: true
  reject_if_type_mismatch: true
  calculate_sha256: true
  safe_decode: true
temporary_storage:
  root_path: "runtime/temp"
  ttl_minutes: 60
  cleanup_retries: 3
  quarantine_enabled: true
  quarantine_ttl_hours: 24
preprocessing:
  image:
    extract_metadata: true
    normalize_for_analysis: true
  audio:
    extract_metadata: true
    fragment_duration_seconds: 10
    build_spectrogram: true
  video:
    extract_metadata: true
    keyframe_interval_seconds: 2
    extract_audio_track: true
analyzers:
  defaults:
    timeout_seconds: 120
    continue_on_error: true
  image:
    enabled: []
  audio:
    enabled: []
  video:
    enabled: []
  settings: {}
risk_assessment:
  model_id: "score_model_v1"
  model_version: "0.1.0"
  thresholds:
    low_max: 29
    medium_max: 60
  severity_scores:
    weak: 5
    significant: 25
  critical_override:
    enabled: false
    allowed_finding_types: []
  completeness:
    minimum_for_assessment: 0.5
result:
  directory: "runtime/results"
  atomic_write: true
  include_raw_metrics: false
  store_original_name: true
error_handling:
  continue_if_analyzer_fails: true
  mark_partial_on_analyzer_failure: true
  hide_internal_error_details: true
logging:
  level: "INFO"
  jsonl_path: "runtime/logs/application.jsonl"
  rotation_max_bytes: 10485760
  rotation_backup_count: 5
external_systems:
  enabled: false
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_content)
        tmp_path = f.name

    try:
        config = load_config(tmp_path)
        assert isinstance(config, AppConfig)
        assert config.schema_version == "1.0"
        assert config.server.host == "0.0.0.0"
        assert config.server.port == 9090
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_unknown_field_rejected() -> None:
    """A YAML file with an unknown top-level field raises ConfigurationError."""
    yaml_content = """\
schema_version: "1.0"
server:
  host: "127.0.0.1"
  port: 8080
access_channels:
  webui:
    enabled: true
    require_authentication: true
  api:
    enabled: true
    require_token: true
    token_env_var: "MEDIA_ANALYZER_API_TOKEN"
limits:
  max_file_size_mb:
    image: 20
    audio: 50
    video: 200
  max_parallel_tasks:
    image: 4
    audio: 2
    video: 1
  processing_timeout_seconds: 600
allowed_formats:
  image:
    extensions: ["jpg", "jpeg", "png", "webp"]
    mime_types: ["image/jpeg", "image/png", "image/webp"]
  audio:
    extensions: ["wav", "mp3", "flac", "m4a"]
    mime_types: ["audio/wav", "audio/mpeg", "audio/flac", "audio/mp4"]
  video:
    extensions: ["mp4", "mov", "avi", "mkv"]
    mime_types: ["video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska"]
validation:
  check_extension: true
  check_mime_type: true
  check_file_signature: true
  reject_if_type_mismatch: true
  calculate_sha256: true
  safe_decode: true
temporary_storage:
  root_path: "runtime/temp"
  ttl_minutes: 60
  cleanup_retries: 3
  quarantine_enabled: true
  quarantine_ttl_hours: 24
preprocessing:
  image:
    extract_metadata: true
    normalize_for_analysis: true
  audio:
    extract_metadata: true
    fragment_duration_seconds: 10
    build_spectrogram: true
  video:
    extract_metadata: true
    keyframe_interval_seconds: 2
    extract_audio_track: true
analyzers:
  defaults:
    timeout_seconds: 120
    continue_on_error: true
  image:
    enabled: []
  audio:
    enabled: []
  video:
    enabled: []
  settings: {}
risk_assessment:
  model_id: "score_model_v1"
  model_version: "0.1.0"
  thresholds:
    low_max: 29
    medium_max: 60
  severity_scores:
    weak: 5
    significant: 25
  critical_override:
    enabled: false
    allowed_finding_types: []
  completeness:
    minimum_for_assessment: 0.5
result:
  directory: "runtime/results"
  atomic_write: true
  include_raw_metrics: false
  store_original_name: true
error_handling:
  continue_if_analyzer_fails: true
  mark_partial_on_analyzer_failure: true
  hide_internal_error_details: true
logging:
  level: "INFO"
  jsonl_path: "runtime/logs/application.jsonl"
  rotation_max_bytes: 10485760
  rotation_backup_count: 5
external_systems:
  enabled: false
unknown_section:
  foo: bar
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_content)
        tmp_path = f.name

    try:
        with pytest.raises(ConfigurationError, match="validation failed"):
            load_config(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Environment variable override tests
# ---------------------------------------------------------------------------

_MINIMAL_YAML = """\
schema_version: "1.0"
server:
  host: "127.0.0.1"
  port: 8080
access_channels:
  webui:
    enabled: true
    require_authentication: true
  api:
    enabled: true
    require_token: true
    token_env_var: "MEDIA_ANALYZER_API_TOKEN"
limits:
  max_file_size_mb:
    image: 20
    audio: 50
    video: 200
  max_parallel_tasks:
    image: 4
    audio: 2
    video: 1
  processing_timeout_seconds: 600
allowed_formats:
  image:
    extensions: ["jpg", "jpeg", "png", "webp"]
    mime_types: ["image/jpeg", "image/png", "image/webp"]
  audio:
    extensions: ["wav", "mp3", "flac", "m4a"]
    mime_types: ["audio/wav", "audio/mpeg", "audio/flac", "audio/mp4"]
  video:
    extensions: ["mp4", "mov", "avi", "mkv"]
    mime_types: ["video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska"]
validation:
  check_extension: true
  check_mime_type: true
  check_file_signature: true
  reject_if_type_mismatch: true
  calculate_sha256: true
  safe_decode: true
temporary_storage:
  root_path: "runtime/temp"
  ttl_minutes: 60
  cleanup_retries: 3
  quarantine_enabled: true
  quarantine_ttl_hours: 24
preprocessing:
  image:
    extract_metadata: true
    normalize_for_analysis: true
  audio:
    extract_metadata: true
    fragment_duration_seconds: 10
    build_spectrogram: true
  video:
    extract_metadata: true
    keyframe_interval_seconds: 2
    extract_audio_track: true
analyzers:
  defaults:
    timeout_seconds: 120
    continue_on_error: true
  image:
    enabled: []
  audio:
    enabled: []
  video:
    enabled: []
  settings: {}
risk_assessment:
  model_id: "score_model_v1"
  model_version: "0.1.0"
  thresholds:
    low_max: 29
    medium_max: 60
  severity_scores:
    weak: 5
    significant: 25
  critical_override:
    enabled: false
    allowed_finding_types: []
  completeness:
    minimum_for_assessment: 0.5
result:
  directory: "runtime/results"
  atomic_write: true
  include_raw_metrics: false
  store_original_name: true
error_handling:
  continue_if_analyzer_fails: true
  mark_partial_on_analyzer_failure: true
  hide_internal_error_details: true
logging:
  level: "INFO"
  jsonl_path: "runtime/logs/application.jsonl"
  rotation_max_bytes: 10485760
  rotation_backup_count: 5
external_systems:
  enabled: false
"""


def _write_temp_yaml(content: str) -> str:
    """Write *content* to a temporary ``.yaml`` file and return its path."""
    import tempfile

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        return f.name


def test_no_env_uses_yaml_value() -> None:
    """When no FAKEDETECTOR_ vars are set, the YAML value is used as-is."""
    tmp_path = _write_temp_yaml(_MINIMAL_YAML)
    try:
        config = load_config(tmp_path, env={})
        assert config.server.host == "127.0.0.1"
        assert config.server.port == 8080
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.parametrize(
    "level",
    ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
)
def test_standard_logging_levels_are_valid(level: str) -> None:
    config = LoggingConfig.model_validate({"level": level})

    assert config.level == level


def test_lowercase_logging_level_is_normalized() -> None:
    config = LoggingConfig.model_validate({"level": "debug"})

    assert config.level == "DEBUG"


def test_unsupported_yaml_logging_level_is_rejected_safely() -> None:
    unsupported_level = "unsafe-custom-level"
    yaml_content = _MINIMAL_YAML.replace(
        'level: "INFO"',
        f'level: "{unsupported_level}"',
    )
    tmp_path = _write_temp_yaml(yaml_content)
    try:
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(tmp_path, env={})

        error = exc_info.value
        traceback_text = "".join(traceback.format_exception(error))
        assert unsupported_level not in str(error)
        assert unsupported_level not in traceback_text
        assert error.__cause__ is None
        assert error.__context__ is None
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_unsupported_env_logging_level_is_rejected_safely() -> None:
    unsupported_level = "unsafe-env-level"
    tmp_path = _write_temp_yaml(_MINIMAL_YAML)
    try:
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(
                tmp_path,
                env={"FAKEDETECTOR_LOGGING__LEVEL": unsupported_level},
            )

        error = exc_info.value
        traceback_text = "".join(traceback.format_exception(error))
        assert unsupported_level not in str(error)
        assert unsupported_level not in traceback_text
        assert error.__cause__ is None
        assert error.__context__ is None
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_env_overrides_server_host() -> None:
    """FAKEDETECTOR_SERVER__HOST overrides the YAML host value."""
    tmp_path = _write_temp_yaml(_MINIMAL_YAML)
    try:
        config = load_config(
            tmp_path,
            env={"FAKEDETECTOR_SERVER__HOST": "0.0.0.0"},
        )
        assert config.server.host == "0.0.0.0"
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_env_server_port_converted_to_int() -> None:
    """FAKEDETECTOR_SERVER__PORT with a numeric string becomes an int."""
    tmp_path = _write_temp_yaml(_MINIMAL_YAML)
    try:
        config = load_config(
            tmp_path,
            env={"FAKEDETECTOR_SERVER__PORT": "9090"},
        )
        assert config.server.port == 9090
        assert isinstance(config.server.port, int)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_env_bool_override() -> None:
    """Boolean settings can be overridden via env var."""
    tmp_path = _write_temp_yaml(_MINIMAL_YAML)
    try:
        config = load_config(
            tmp_path,
            env={"FAKEDETECTOR_VALIDATION__CHECK_EXTENSION": "false"},
        )
        assert config.validation.check_extension is False
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_env_without_prefix_ignored() -> None:
    """Variables that do not start with FAKEDETECTOR_ are silently ignored."""
    tmp_path = _write_temp_yaml(_MINIMAL_YAML)
    try:
        config = load_config(
            tmp_path,
            env={
                "SERVER__HOST": "10.0.0.1",
                "FAKEDETECTOR_SERVER__HOST": "192.168.1.1",
            },
        )
        # The unprefixed var is ignored; the prefixed one takes effect.
        assert config.server.host == "192.168.1.1"
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_unknown_fakedetector_path_rejected() -> None:
    """A FAKEDETECTOR_ variable pointing to an unknown field raises
    ConfigurationError (extra fields are forbidden by the Pydantic models).
    """
    tmp_path = _write_temp_yaml(_MINIMAL_YAML)
    try:
        with pytest.raises(ConfigurationError, match="environment variable"):
            load_config(
                tmp_path,
                env={"FAKEDETECTOR_SERVER__NONEXISTENT": "value"},
            )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_invalid_env_value_raises_configuration_error() -> None:
    """An env var that yields an invalid Pydantic type raises ConfigurationError."""
    tmp_path = _write_temp_yaml(_MINIMAL_YAML)
    try:
        with pytest.raises(ConfigurationError, match="environment variable"):
            load_config(
                tmp_path,
                env={"FAKEDETECTOR_SERVER__PORT": "not_a_number"},
            )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_error_message_does_not_leak_secret_value() -> None:
    """The ConfigurationError message must not contain the raw env-var value."""
    tmp_path = _write_temp_yaml(_MINIMAL_YAML)
    # Use a secret-like value that should never appear in plain text in
    # the error message.
    secret_value = "s3cret-t0ken-DO-NOT-LEAK"
    try:
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(
                tmp_path,
                env={"FAKEDETECTOR_UNKNOWN__TOP__KEY": secret_value},
            )
        error_text = str(exc_info.value)
        assert secret_value not in error_text, (
            f"Error message leaked secret value: {error_text}"
        )
        # But the misbehaving variable name *is* safe to mention.
        assert "FAKEDETECTOR_UNKNOWN__TOP__KEY" in error_text
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_invalid_field_type_rejected() -> None:
    """A field with an invalid type (e.g. string instead of int) raises ConfigurationError."""
    yaml_content = """\
schema_version: "1.0"
server:
  host: "127.0.0.1"
  port: "not_a_number"
access_channels:
  webui:
    enabled: true
    require_authentication: true
  api:
    enabled: true
    require_token: true
    token_env_var: "MEDIA_ANALYZER_API_TOKEN"
limits:
  max_file_size_mb:
    image: 20
    audio: 50
    video: 200
  max_parallel_tasks:
    image: 4
    audio: 2
    video: 1
  processing_timeout_seconds: 600
allowed_formats:
  image:
    extensions: ["jpg", "jpeg", "png", "webp"]
    mime_types: ["image/jpeg", "image/png", "image/webp"]
  audio:
    extensions: ["wav", "mp3", "flac", "m4a"]
    mime_types: ["audio/wav", "audio/mpeg", "audio/flac", "audio/mp4"]
  video:
    extensions: ["mp4", "mov", "avi", "mkv"]
    mime_types: ["video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska"]
validation:
  check_extension: true
  check_mime_type: true
  check_file_signature: true
  reject_if_type_mismatch: true
  calculate_sha256: true
  safe_decode: true
temporary_storage:
  root_path: "runtime/temp"
  ttl_minutes: 60
  cleanup_retries: 3
  quarantine_enabled: true
  quarantine_ttl_hours: 24
preprocessing:
  image:
    extract_metadata: true
    normalize_for_analysis: true
  audio:
    extract_metadata: true
    fragment_duration_seconds: 10
    build_spectrogram: true
  video:
    extract_metadata: true
    keyframe_interval_seconds: 2
    extract_audio_track: true
analyzers:
  defaults:
    timeout_seconds: 120
    continue_on_error: true
  image:
    enabled: []
  audio:
    enabled: []
  video:
    enabled: []
  settings: {}
risk_assessment:
  model_id: "score_model_v1"
  model_version: "0.1.0"
  thresholds:
    low_max: 29
    medium_max: 60
  severity_scores:
    weak: 5
    significant: 25
  critical_override:
    enabled: false
    allowed_finding_types: []
  completeness:
    minimum_for_assessment: 0.5
result:
  directory: "runtime/results"
  atomic_write: true
  include_raw_metrics: false
  store_original_name: true
error_handling:
  continue_if_analyzer_fails: true
  mark_partial_on_analyzer_failure: true
  hide_internal_error_details: true
logging:
  level: "INFO"
  jsonl_path: "runtime/logs/application.jsonl"
  rotation_max_bytes: 10485760
  rotation_backup_count: 5
external_systems:
  enabled: false
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_content)
        tmp_path = f.name

    try:
        with pytest.raises(ConfigurationError, match="validation failed"):
            load_config(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_invalid_yaml_raises_controlled_error() -> None:
    """Malformed YAML raises ConfigurationError, not a raw YAML exception."""
    yaml_content = """\
schema_version: "1.0"
server:
  host: "127.0.0.1"
  port: [unclosed
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_content)
        tmp_path = f.name

    try:
        with pytest.raises(ConfigurationError, match="invalid YAML"):
            load_config(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_missing_file_raises_controlled_error() -> None:
    """A non-existent file path raises ConfigurationError."""
    with pytest.raises(ConfigurationError, match="not found"):
        load_config("nonexistent_config_12345.yaml")


def test_full_example_config_loads() -> None:
    """The config.example.yaml file loads without errors."""
    example_path = Path("config/config.example.yaml")
    assert example_path.is_file(), "config.example.yaml must exist"
    config = load_config(str(example_path))
    assert isinstance(config, AppConfig)
    assert config.schema_version == "1.0"


def test_unknown_nested_field_rejected() -> None:
    """An unknown field inside a known section raises ConfigurationError."""
    yaml_content = """\
schema_version: "1.0"
server:
  host: "127.0.0.1"
  port: 8080
  unknown_server_field: true
access_channels:
  webui:
    enabled: true
    require_authentication: true
  api:
    enabled: true
    require_token: true
    token_env_var: "MEDIA_ANALYZER_API_TOKEN"
limits:
  max_file_size_mb:
    image: 20
    audio: 50
    video: 200
  max_parallel_tasks:
    image: 4
    audio: 2
    video: 1
  processing_timeout_seconds: 600
allowed_formats:
  image:
    extensions: ["jpg", "jpeg", "png", "webp"]
    mime_types: ["image/jpeg", "image/png", "image/webp"]
  audio:
    extensions: ["wav", "mp3", "flac", "m4a"]
    mime_types: ["audio/wav", "audio/mpeg", "audio/flac", "audio/mp4"]
  video:
    extensions: ["mp4", "mov", "avi", "mkv"]
    mime_types: ["video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska"]
validation:
  check_extension: true
  check_mime_type: true
  check_file_signature: true
  reject_if_type_mismatch: true
  calculate_sha256: true
  safe_decode: true
temporary_storage:
  root_path: "runtime/temp"
  ttl_minutes: 60
  cleanup_retries: 3
  quarantine_enabled: true
  quarantine_ttl_hours: 24
preprocessing:
  image:
    extract_metadata: true
    normalize_for_analysis: true
  audio:
    extract_metadata: true
    fragment_duration_seconds: 10
    build_spectrogram: true
  video:
    extract_metadata: true
    keyframe_interval_seconds: 2
    extract_audio_track: true
analyzers:
  defaults:
    timeout_seconds: 120
    continue_on_error: true
  image:
    enabled: []
  audio:
    enabled: []
  video:
    enabled: []
  settings: {}
risk_assessment:
  model_id: "score_model_v1"
  model_version: "0.1.0"
  thresholds:
    low_max: 29
    medium_max: 60
  severity_scores:
    weak: 5
    significant: 25
  critical_override:
    enabled: false
    allowed_finding_types: []
  completeness:
    minimum_for_assessment: 0.5
result:
  directory: "runtime/results"
  atomic_write: true
  include_raw_metrics: false
  store_original_name: true
error_handling:
  continue_if_analyzer_fails: true
  mark_partial_on_analyzer_failure: true
  hide_internal_error_details: true
logging:
  level: "INFO"
  jsonl_path: "runtime/logs/application.jsonl"
  rotation_max_bytes: 10485760
  rotation_backup_count: 5
external_systems:
  enabled: false
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_content)
        tmp_path = f.name

    try:
        with pytest.raises(ConfigurationError, match="validation failed"):
            load_config(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_empty_yaml_rejected() -> None:
    """An empty YAML file is rejected because all sections are required."""
    yaml_content = """\
schema_version: "1.0"
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_content)
        tmp_path = f.name

    try:
        with pytest.raises(ConfigurationError, match="validation failed"):
            load_config(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_missing_required_section_rejected() -> None:
    """A YAML file missing a required top-level section raises ConfigurationError."""
    yaml_content = """\
schema_version: "1.0"
server:
  host: "127.0.0.1"
  port: 8080
access_channels:
  webui:
    enabled: true
    require_authentication: true
  api:
    enabled: true
    require_token: true
    token_env_var: "MEDIA_ANALYZER_API_TOKEN"
limits:
  max_file_size_mb:
    image: 20
    audio: 50
    video: 200
  max_parallel_tasks:
    image: 4
    audio: 2
    video: 1
  processing_timeout_seconds: 600
allowed_formats:
  image:
    extensions: ["jpg", "jpeg", "png", "webp"]
    mime_types: ["image/jpeg", "image/png", "image/webp"]
  audio:
    extensions: ["wav", "mp3", "flac", "m4a"]
    mime_types: ["audio/wav", "audio/mpeg", "audio/flac", "audio/mp4"]
  video:
    extensions: ["mp4", "mov", "avi", "mkv"]
    mime_types: ["video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska"]
validation:
  check_extension: true
  check_mime_type: true
  check_file_signature: true
  reject_if_type_mismatch: true
  calculate_sha256: true
  safe_decode: true
temporary_storage:
  root_path: "runtime/temp"
  ttl_minutes: 60
  cleanup_retries: 3
  quarantine_enabled: true
  quarantine_ttl_hours: 24
preprocessing:
  image:
    extract_metadata: true
    normalize_for_analysis: true
  audio:
    extract_metadata: true
    fragment_duration_seconds: 10
    build_spectrogram: true
  video:
    extract_metadata: true
    keyframe_interval_seconds: 2
    extract_audio_track: true
analyzers:
  defaults:
    timeout_seconds: 120
    continue_on_error: true
  image:
    enabled: []
  audio:
    enabled: []
  video:
    enabled: []
  settings: {}
risk_assessment:
  model_id: "score_model_v1"
  model_version: "0.1.0"
  thresholds:
    low_max: 29
    medium_max: 60
  severity_scores:
    weak: 5
    significant: 25
  critical_override:
    enabled: false
    allowed_finding_types: []
  completeness:
    minimum_for_assessment: 0.5
result:
  directory: "runtime/results"
  atomic_write: true
  include_raw_metrics: false
  store_original_name: true
error_handling:
  continue_if_analyzer_fails: true
  mark_partial_on_analyzer_failure: true
  hide_internal_error_details: true
logging:
  level: "INFO"
  jsonl_path: "runtime/logs/application.jsonl"
  rotation_max_bytes: 10485760
  rotation_backup_count: 5
# external_systems is missing
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_content)
        tmp_path = f.name

    try:
        with pytest.raises(ConfigurationError, match="validation failed"):
            load_config(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_unsupported_schema_version_rejected() -> None:
    """A schema_version other than '1.0' raises ConfigurationError."""
    yaml_content = """\
schema_version: "2.0"
server:
  host: "127.0.0.1"
  port: 8080
access_channels:
  webui:
    enabled: true
    require_authentication: true
  api:
    enabled: true
    require_token: true
    token_env_var: "MEDIA_ANALYZER_API_TOKEN"
limits:
  max_file_size_mb:
    image: 20
    audio: 50
    video: 200
  max_parallel_tasks:
    image: 4
    audio: 2
    video: 1
  processing_timeout_seconds: 600
allowed_formats:
  image:
    extensions: ["jpg", "jpeg", "png", "webp"]
    mime_types: ["image/jpeg", "image/png", "image/webp"]
  audio:
    extensions: ["wav", "mp3", "flac", "m4a"]
    mime_types: ["audio/wav", "audio/mpeg", "audio/flac", "audio/mp4"]
  video:
    extensions: ["mp4", "mov", "avi", "mkv"]
    mime_types: ["video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska"]
validation:
  check_extension: true
  check_mime_type: true
  check_file_signature: true
  reject_if_type_mismatch: true
  calculate_sha256: true
  safe_decode: true
temporary_storage:
  root_path: "runtime/temp"
  ttl_minutes: 60
  cleanup_retries: 3
  quarantine_enabled: true
  quarantine_ttl_hours: 24
preprocessing:
  image:
    extract_metadata: true
    normalize_for_analysis: true
  audio:
    extract_metadata: true
    fragment_duration_seconds: 10
    build_spectrogram: true
  video:
    extract_metadata: true
    keyframe_interval_seconds: 2
    extract_audio_track: true
analyzers:
  defaults:
    timeout_seconds: 120
    continue_on_error: true
  image:
    enabled: []
  audio:
    enabled: []
  video:
    enabled: []
  settings: {}
risk_assessment:
  model_id: "score_model_v1"
  model_version: "0.1.0"
  thresholds:
    low_max: 29
    medium_max: 60
  severity_scores:
    weak: 5
    significant: 25
  critical_override:
    enabled: false
    allowed_finding_types: []
  completeness:
    minimum_for_assessment: 0.5
result:
  directory: "runtime/results"
  atomic_write: true
  include_raw_metrics: false
  store_original_name: true
error_handling:
  continue_if_analyzer_fails: true
  mark_partial_on_analyzer_failure: true
  hide_internal_error_details: true
logging:
  level: "INFO"
  jsonl_path: "runtime/logs/application.jsonl"
  rotation_max_bytes: 10485760
  rotation_backup_count: 5
external_systems:
  enabled: false
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_content)
        tmp_path = f.name

    try:
        with pytest.raises(ConfigurationError, match="validation failed"):
            load_config(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.parametrize(
    "env_name",
    [
        param("FAKEDETECTOR_", id="empty-suffix"),
        param("FAKEDETECTOR_SERVER____PORT", id="empty-middle-segment"),
        param("FAKEDETECTOR___SERVER__PORT", id="empty-leading-segment"),
        param("FAKEDETECTOR_SERVER__PORT__", id="empty-trailing-segment"),
    ],
)
def test_malformed_env_path_rejected(env_name: str) -> None:
    """Environment paths with empty segments raise ConfigurationError."""
    tmp_path = _write_temp_yaml(_MINIMAL_YAML)
    try:
        with pytest.raises(ConfigurationError, match="invalid configuration path"):
            load_config(tmp_path, env={env_name: "9090"})
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_empty_yaml_file_rejected() -> None:
    """A truly empty YAML file is rejected as an incomplete configuration."""
    tmp_path = _write_temp_yaml("")
    try:
        with pytest.raises(ConfigurationError, match="validation failed"):
            load_config(tmp_path, env={})
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_non_utf8_yaml_rejected_as_configuration_error() -> None:
    """Invalid UTF-8 bytes are converted to a safe ConfigurationError."""
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        f.write(b"\xff\xfe\x00")
        tmp_path = Path(f.name)

    try:
        with pytest.raises(ConfigurationError, match="not valid UTF-8"):
            load_config(tmp_path, env={})
    finally:
        tmp_path.unlink(missing_ok=True)


def test_env_mapping_is_not_mutated() -> None:
    """The caller-provided environment mapping remains unchanged."""
    tmp_path = _write_temp_yaml(_MINIMAL_YAML)
    env = {"FAKEDETECTOR_SERVER__PORT": "9090"}
    original_env = env.copy()
    try:
        load_config(tmp_path, env=env)
        assert env == original_env
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_nested_defaults_are_applied() -> None:
    """Documented nested defaults apply when a root section is empty."""
    yaml_content = _MINIMAL_YAML.replace(
        "server:\n  host: \"127.0.0.1\"\n  port: 8080",
        "server: {}",
    )
    tmp_path = _write_temp_yaml(yaml_content)
    try:
        config = load_config(tmp_path, env={})
        assert config.server.host == "127.0.0.1"
        assert config.server.port == 8080
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_configuration_error_chain_does_not_leak_env_value() -> None:
    """No exception representation or traceback contains an env value."""
    tmp_path = _write_temp_yaml(_MINIMAL_YAML)
    secret_value = "secret-value-must-not-leak"
    try:
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(
                tmp_path,
                env={"FAKEDETECTOR_SERVER__PORT": secret_value},
            )

        error = exc_info.value
        chain_text = ""
        current: BaseException | None = error
        while current is not None:
            chain_text += repr(current)
            current = current.__cause__ or current.__context__
        traceback_text = "".join(traceback.format_exception(error))

        assert secret_value not in str(error)
        assert secret_value not in repr(error)
        assert secret_value not in traceback_text
        assert secret_value not in chain_text
        assert error.__cause__ is None
        assert error.__context__ is None
    finally:
        Path(tmp_path).unlink(missing_ok=True)
