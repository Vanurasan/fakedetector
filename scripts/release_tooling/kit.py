"""Exact recipient inventory, manifest, hashes and safe ZIP extraction."""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from . import common

_MANIFEST_NAME = "release-manifest.json"


_COMPANION_SOURCES = {
    "LICENSE": Path("LICENSE"),
    "config.example.yaml": Path("config/config.example.yaml"),
    ".env.example": Path(".env.example"),
    "generate_release_demo_media.py": Path("scripts/generate_release_demo_media.py"),
    "MVP_HANDOFF.md": Path("docs/MVP_HANDOFF.md"),
    "CHANGELOG.md": Path("docs/CHANGELOG.md"),
}


def _expected_kit_names(wheel_filename: str) -> set[str]:
    return {
        wheel_filename,
        "runtime-constraints.txt",
        *_COMPANION_SOURCES,
        _MANIFEST_NAME,
    }


def _validate_kit_inventory(actual_names: set[str], expected_names: set[str]) -> None:
    missing = sorted(expected_names - actual_names)
    unexpected = sorted(actual_names - expected_names)
    if missing or unexpected:
        raise common.ReleaseVerificationError(
            "release_kit",
            "Release kit inventory differs from the required inventory: "
            + json.dumps({"missing": missing, "unexpected": unexpected}, sort_keys=True),
        )


def _validate_zip_member_names(names: list[str], expected_names: set[str]) -> None:
    if len(names) != len(set(names)):
        raise common.ReleaseVerificationError("zip", "ZIP contains duplicate member names.")
    for name in names:
        path = PurePosixPath(name)
        if (
            not name
            or "\\" in name
            or path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
            or ":" in path.parts[0]
        ):
            raise common.ReleaseVerificationError("zip", f"Unsafe ZIP member name: {name!r}.")
    _validate_kit_inventory(set(names), expected_names)


def _build_manifest(
    *,
    product_name: str,
    package_version: str,
    source_head_sha: str,
    source_tree_clean_at_build_start: bool,
    certification_mode: str,
    python_version: str,
    uv_version: str,
    build_backend: str,
    build_requirements: list[str],
    wheel_filename: str,
    file_hashes: dict[str, str],
    ffmpeg_version: str,
    ffprobe_version: str,
) -> dict[str, Any]:
    companion_names = sorted(name for name in file_hashes if name != wheel_filename)
    development = certification_mode == "development"
    artifact_set_claim = (
        "This manifest identifies a non-certifying development candidate and records "
        "the source HEAD SHA and working-tree state observed at build start; uncommitted "
        "changes may be present."
        if development
        else "This manifest identifies a strict certification candidate built from a source "
        "tree that was clean at build start at the recorded HEAD SHA; certification is "
        "authoritative only when the final verification report passes."
    )
    return {
        "manifest_schema_version": "1.0",
        "product_name": product_name,
        "package_version": package_version,
        "source": {
            "head_sha_at_build_start": source_head_sha,
            "tree_clean_at_build_start": source_tree_clean_at_build_start,
        },
        "certification_mode": certification_mode,
        "candidate_nature": (
            "non-certifying development candidate"
            if development
            else "strict certification candidate"
        ),
        "supported_platform": {
            "operating_system": "Windows 11",
            "architecture": "x64",
            "execution": "CPU-only",
        },
        "python": {
            "target": "3.12",
            "verification_version": python_version,
        },
        "build": {
            "uv_version": uv_version,
            "backend": build_backend,
            "backend_requirements": build_requirements,
        },
        "wheel": {
            "filename": wheel_filename,
            "sha256": file_hashes[wheel_filename],
        },
        "runtime_constraints": {
            "filename": "runtime-constraints.txt",
            "sha256": file_hashes["runtime-constraints.txt"],
            "source": "mechanically exported from uv.lock",
        },
        "required_companion_files": [
            {"path": name, "sha256": file_hashes[name]} for name in companion_names
        ],
        "covered_files": [
            {"path": name, "sha256": file_hashes[name]} for name in sorted(file_hashes)
        ],
        "release_notes": {
            "path": "CHANGELOG.md",
            "canonical_source": "docs/CHANGELOG.md",
            "source_head_sha_at_build_start": source_head_sha,
        },
        "external_media_tools": {
            "ffmpeg": {"version": ffmpeg_version},
            "ffprobe": {"version": ffprobe_version},
            "bundled": False,
        },
        "release_gate": {
            "tool": "verify_release.py",
            "tool_version": common._TOOL_VERSION,
        },
        "hash_algorithm": "SHA-256",
        "artifact_set_claim": artifact_set_claim,
        "manifest_self_hash": None,
    }


def _copy_new(source: Path, destination: Path) -> None:
    try:
        with source.open("rb") as input_stream, destination.open("xb") as output_stream:
            shutil.copyfileobj(input_stream, output_stream)
    except OSError:
        raise common.ReleaseVerificationError(
            "release_kit", "A release-kit file could not be copied."
        ) from None


def _assemble_release_kit(
    *,
    repository: Path,
    output: Path,
    project_name: str,
    wheel: Path,
    constraints: Path,
    manifest_arguments: dict[str, Any],
) -> tuple[Path, dict[str, Any], str, dict[str, str]]:
    kit = output / f"{project_name}-{manifest_arguments['package_version']}"
    kit.mkdir()
    _copy_new(wheel, kit / wheel.name)
    _copy_new(constraints, kit / "runtime-constraints.txt")
    for destination_name, relative_source in _COMPANION_SOURCES.items():
        _copy_new(repository / relative_source, kit / destination_name)

    file_hashes = {
        path.name: common._sha256_file(path)
        for path in kit.iterdir()
        if path.is_file() and path.name != _MANIFEST_NAME
    }
    manifest = _build_manifest(
        wheel_filename=wheel.name,
        file_hashes=file_hashes,
        **manifest_arguments,
    )
    manifest_path = kit / _MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    expected_names = _expected_kit_names(wheel.name)
    actual_names = {path.name for path in kit.iterdir() if path.is_file()}
    _validate_kit_inventory(actual_names, expected_names)
    if any(path.is_dir() for path in kit.iterdir()):
        raise common.ReleaseVerificationError(
            "release_kit", "Release kit contains an unexpected directory."
        )
    return kit, manifest, common._sha256_file(manifest_path), file_hashes


def _create_zip(kit: Path, zip_path: Path, expected_names: set[str]) -> None:
    with zipfile.ZipFile(zip_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(expected_names):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (kit / name).read_bytes())


def _verify_zip(
    *,
    zip_path: Path,
    output: Path,
    expected_names: set[str],
    manifest: dict[str, Any],
    manifest_sha256: str,
) -> tuple[Path, dict[str, Any]]:
    extraction = output / "verified-zip-extraction"
    extraction.mkdir()
    manifest_hashes = {item["path"]: item["sha256"] for item in manifest["covered_files"]}
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        _validate_zip_member_names(names, expected_names)
        for name in names:
            payload = archive.read(name)
            if name == _MANIFEST_NAME:
                if common._sha256_bytes(payload) != manifest_sha256:
                    raise common.ReleaseVerificationError(
                        "zip", "Manifest bytes differ inside the ZIP."
                    )
            elif common._sha256_bytes(payload) != manifest_hashes.get(name):
                raise common.ReleaseVerificationError("zip", f"ZIP hash mismatch for {name}.")
            target = extraction / name
            with target.open("xb") as stream:
                stream.write(payload)
    extracted_manifest = json.loads((extraction / _MANIFEST_NAME).read_text(encoding="utf-8"))
    if extracted_manifest != manifest:
        raise common.ReleaseVerificationError("zip", "Extracted manifest differs semantically.")
    for name, expected_hash in manifest_hashes.items():
        if common._sha256_file(extraction / name) != expected_hash:
            raise common.ReleaseVerificationError(
                "zip", f"Extracted file hash mismatch for {name}."
            )
    return extraction, {
        "status": "passed",
        "safe_member_names": True,
        "inventory_match": True,
        "hashes_match": True,
        "clean_extraction": True,
        "entry_count": len(expected_names),
    }
