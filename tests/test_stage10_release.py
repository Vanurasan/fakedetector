"""Fast regression tests for the Stage 10 Macro 3 release gate."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "verify_stage10_release.py"


def _load_release_gate() -> ModuleType:
    scripts_directory = str(_SCRIPT.parent)
    if scripts_directory not in sys.path:
        sys.path.insert(0, scripts_directory)
    spec = importlib.util.spec_from_file_location("stage10_release_gate", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def release_gate() -> ModuleType:
    return _load_release_gate()


def test_sha256_file_hashes_exact_bytes(tmp_path: Path, release_gate: ModuleType) -> None:
    path = tmp_path / "artifact.bin"
    payload = b"stage-10-release-artifact\x00\xff"
    path.write_bytes(payload)

    assert release_gate._sha256_file(path) == hashlib.sha256(payload).hexdigest()


def test_certification_decision_is_strict_by_default(release_gate: ModuleType) -> None:
    strict = release_gate._certification_state(development=False, source_status=[])

    assert strict == {
        "certification_mode": "strict",
        "source_tree_clean": True,
        "certified": True,
    }
    with pytest.raises(release_gate.ReleaseGateError, match="clean"):
        release_gate._certification_state(
            development=False,
            source_status=[" M scripts/verify_stage10_release.py"],
        )


def test_development_mode_is_explicitly_non_certifying(release_gate: ModuleType) -> None:
    state = release_gate._certification_state(
        development=True,
        source_status=["?? tests/test_stage10_release.py"],
    )

    assert state == {
        "certification_mode": "development",
        "source_tree_clean": False,
        "certified": False,
    }


def test_supported_host_accepts_windows_11_x64_python_312(
    release_gate: ModuleType,
) -> None:
    release_gate._validate_supported_host(
        platform_name="win32",
        machine="AMD64",
        python_version=(3, 12),
        windows_major=10,
        windows_build=22000,
        windows_product_type=1,
    )


@pytest.mark.parametrize(
    (
        "machine",
        "python_version",
        "windows_major",
        "windows_build",
        "windows_product_type",
    ),
    [
        ("AMD64", (3, 12), 10, 19045, 1),
        ("ARM64", (3, 12), 10, 22631, 1),
        ("AMD64", (3, 11), 10, 22631, 1),
        ("AMD64", (3, 12), 6, 22631, 1),
        ("AMD64", (3, 12), 10, 22631, 2),
    ],
)
def test_supported_host_rejects_unsupported_windows_matrix(
    release_gate: ModuleType,
    machine: str,
    python_version: tuple[int, int],
    windows_major: int,
    windows_build: int,
    windows_product_type: int,
) -> None:
    with pytest.raises(release_gate.ReleaseGateError, match="Windows 11 x64"):
        release_gate._validate_supported_host(
            platform_name="win32",
            machine=machine,
            python_version=python_version,
            windows_major=windows_major,
            windows_build=windows_build,
            windows_product_type=windows_product_type,
        )


def test_supported_host_rejects_server_despite_high_windows_build(
    release_gate: ModuleType,
) -> None:
    with pytest.raises(release_gate.ReleaseGateError, match="workstation"):
        release_gate._validate_supported_host(
            platform_name="win32",
            machine="AMD64",
            python_version=(3, 12),
            windows_major=10,
            windows_build=26100,
            windows_product_type=3,
        )


def test_graceful_exit_code_accepts_observed_windows_ctrl_break_code(
    release_gate: ModuleType,
) -> None:
    release_gate._validate_graceful_exit_code(
        returncode=3,
        signal_method="CTRL_BREAK_EVENT",
        platform_name="win32",
    )


@pytest.mark.parametrize("returncode", [0, 42, 3221225477, -9])
def test_graceful_exit_code_rejects_unexpected_windows_codes(
    release_gate: ModuleType,
    returncode: int,
) -> None:
    with pytest.raises(release_gate.ReleaseGateError, match="Unexpected") as caught:
        release_gate._validate_graceful_exit_code(
            returncode=returncode,
            signal_method="CTRL_BREAK_EVENT",
            platform_name="win32",
        )

    assert caught.value.process_returncode == returncode


def test_graceful_exit_code_uses_narrow_non_windows_policy(
    release_gate: ModuleType,
) -> None:
    release_gate._validate_graceful_exit_code(
        returncode=0,
        signal_method="SIGINT",
        platform_name="linux",
    )
    with pytest.raises(release_gate.ReleaseGateError, match="Unexpected"):
        release_gate._validate_graceful_exit_code(
            returncode=-2,
            signal_method="SIGINT",
            platform_name="linux",
        )


def test_project_identity_has_no_release_tool_version_source(release_gate: ModuleType) -> None:
    assert release_gate._project_identity(
        {"project": {"name": "sample-product", "version": "7.8.9"}}
    ) == ("sample-product", "7.8.9")
    assert not hasattr(release_gate, "_PACKAGE_VERSION")


def test_final_source_integrity_rejects_changed_head(release_gate: ModuleType) -> None:
    release_gate._require_stable_source_sha(initial_sha="a" * 40, final_sha="a" * 40)

    with pytest.raises(release_gate.ReleaseGateError, match="HEAD changed"):
        release_gate._require_stable_source_sha(initial_sha="a" * 40, final_sha="b" * 40)


def test_manifest_covers_every_recipient_file_without_self_hash(
    release_gate: ModuleType,
) -> None:
    wheel = "sample_product-7.8.9-py3-none-any.whl"
    covered_names = release_gate._expected_kit_names(wheel) - {release_gate._MANIFEST_NAME}
    file_hashes = {name: hashlib.sha256(name.encode()).hexdigest() for name in covered_names}

    manifest = release_gate._build_manifest(
        product_name="sample-product",
        package_version="7.8.9",
        source_head_sha="a" * 40,
        source_tree_clean_at_build_start=False,
        certification_mode="development",
        python_version="3.12.10",
        uv_version="uv 0.8.22",
        build_backend="hatchling.build",
        build_requirements=["hatchling==1.32.3"],
        wheel_filename=wheel,
        file_hashes=file_hashes,
        ffmpeg_version="ffmpeg version test",
        ffprobe_version="ffprobe version test",
    )

    assert manifest["source"] == {
        "head_sha_at_build_start": "a" * 40,
        "tree_clean_at_build_start": False,
    }
    assert manifest["product_name"] == "sample-product"
    assert manifest["package_version"] == "7.8.9"
    assert manifest["certification_mode"] == "development"
    assert manifest["candidate_nature"] == "non-certifying development candidate"
    assert "uncommitted changes may be present" in manifest["artifact_set_claim"]
    assert "tree_clean_at_certification" not in manifest["source"]
    assert manifest["manifest_self_hash"] is None
    assert {item["path"] for item in manifest["covered_files"]} == covered_names
    assert {item["path"] for item in manifest["required_companion_files"]} == (
        covered_names - {wheel}
    )
    assert all(not Path(item["path"]).is_absolute() for item in manifest["covered_files"])


def test_kit_inventory_rejects_missing_and_excluded_content(release_gate: ModuleType) -> None:
    wheel = "sample_product-7.8.9-py3-none-any.whl"
    expected = release_gate._expected_kit_names(wheel)

    release_gate._validate_kit_inventory(set(expected), expected)
    with pytest.raises(release_gate.ReleaseGateError, match="inventory"):
        release_gate._validate_kit_inventory(expected | {"runtime/results/result.json"}, expected)
    with pytest.raises(release_gate.ReleaseGateError, match="inventory"):
        release_gate._validate_kit_inventory(expected - {"MVP_HANDOFF.md"}, expected)


@pytest.mark.parametrize(
    "unsafe_name",
    [
        "../escape.txt",
        "/absolute.txt",
        "C:/absolute.txt",
        "nested/../escape.txt",
        "nested\\escape.txt",
    ],
)
def test_zip_member_validation_rejects_traversal_and_absolute_paths(
    release_gate: ModuleType,
    unsafe_name: str,
) -> None:
    expected = {"release-manifest.json"}

    with pytest.raises(release_gate.ReleaseGateError, match="Unsafe ZIP member"):
        release_gate._validate_zip_member_names([unsafe_name], expected)


def test_zip_member_validation_rejects_duplicates(release_gate: ModuleType) -> None:
    with pytest.raises(release_gate.ReleaseGateError, match="duplicate"):
        release_gate._validate_zip_member_names(
            ["release-manifest.json", "release-manifest.json"],
            {"release-manifest.json"},
        )


def test_failure_redaction_removes_raw_and_derived_auth_material(
    release_gate: ModuleType,
) -> None:
    credentials, basic_header, bearer_header, secret_values = (
        release_gate._auth_headers_and_redaction_values(
            api_token="api-secret",
            webui_username="gate-user",
            webui_password="web-secret",
        )
    )
    basic_payload = basic_header.removeprefix("Basic ")
    message = " ".join(
        (
            "api-secret",
            "gate-user",
            "web-secret",
            credentials,
            basic_payload,
            basic_header,
            bearer_header,
            f"Authorization: {basic_header}",
            f"Authorization: {bearer_header}",
        )
    )

    redacted = release_gate._redact(message, secret_values)

    for secret in secret_values:
        assert secret not in redacted
    assert "<redacted>" in redacted


def test_result_validation_uses_explicit_expected_application_version(
    release_gate: ModuleType,
) -> None:
    result = {
        "schema_version": "1.0",
        "analysis_id": "analysis-id",
        "status": "completed",
        "stage": "finished",
        "completeness": {"status": "complete"},
        "analyzers": [
            {
                "analyzer_id": "audio_pcm_quality",
                "analyzer_version": "1.0.0",
                "status": "completed",
            }
        ],
        "risk_assessment": {"final_level": "unknown"},
        "recommendation": {"text": "review"},
        "cleanup": {"status": "completed"},
        "processing": {"application_version": "7.8.9"},
    }

    evidence = release_gate._validate_result(
        result=result,
        analysis_id="analysis-id",
        suffix=".wav",
        expected_application_version="7.8.9",
    )

    assert evidence["status"] == "passed"
    with pytest.raises(release_gate.ReleaseGateError, match="structural validation"):
        release_gate._validate_result(
            result=result,
            analysis_id="analysis-id",
            suffix=".wav",
            expected_application_version="9.9.9",
        )


def test_initial_report_is_stable_and_non_certifying(release_gate: ModuleType) -> None:
    report = release_gate._initial_report(output=Path("C:/gate"), development=True)

    assert report["tool_version"] == "1.0.0"
    assert report["certification_mode"] == "development"
    assert report["certified"] is False
    assert report["source_sha_at_end"] is None
    assert report["source_sha_stable"] is None
    assert report["overall_status"] == "running"
