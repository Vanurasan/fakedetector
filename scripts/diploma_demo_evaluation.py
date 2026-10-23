"""Frozen first-party demonstration corpus; no calibration or external media.

Run generate --output EXTERNAL_DIR, evaluate --corpus EXTERNAL_DIR, then report
--corpus EXTERNAL_DIR. All media, manifests and results stay outside the checkout.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import io
import json
import math
import os
import platform
import secrets
import shutil
import statistics
import subprocess
import time
import wave
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFilter

from fakedetector.analyzers._catalog import _resolve_runtime_analyzer_definition
from fakedetector.app import create_app
from fakedetector.application import AnalysisApplicationError, AnalysisPendingError
from fakedetector.config.models import AppConfig
from fakedetector.domain import AnalysisResult, MediaType, SourceChannel, SourceContext
from fakedetector.lifecycle._assessment import (
    _ENSEMBLE_FAMILIES,
    _effective_response,
    _ensemble_response,
    _ensemble_score,
    _family_factor,
    _family_response,
    _media_capacity,
)

ROOT = Path(__file__).resolve().parents[1]
GENERATOR_VERSION = "diploma-demo-1.0.0"
BASELINE_HEAD = "4459e795b8d784a4e683487c0d5b3f8e155b8bce"
ASSESSMENT_SHA256 = "0b022e995316fecde23b7afbbeb2f32bb836e7bc973fdd3d0ed86c6fc06a2a1b"
# Exact authorized source deltas, not replacements for the historical fingerprint.
_AASIST_COMPATIBILITY = "aasist-l-measurement-only@1.0.0"
_F01_COMPATIBILITY = "complete-low-wording@1.0.0"
_AASIST_F01_COMPATIBILITY = f"{_AASIST_COMPATIBILITY}+{_F01_COMPATIBILITY}"
_HISTORICAL_LOW_TEXT = (
    '        "Дополнительные действия не требуются; '
    'результат не является окончательной экспертизой.",\n'
)
_F01_LOW_TEXT = """        (
            "По результатам выполненных проверок система не рекомендует дополнительных действий. "
            "Низкий уровень технического риска относится только к проверенным признакам "
            "и не подтверждает подлинность или безопасность файла."
        ),
"""
_HISTORICAL_ID_GUARD = """        if any(result.analyzer_id not in specs for result in results):
            raise ValueError("unknown ensemble analyzer")
"""
_AASIST_ID_GUARD = """        for result in results:
            if result.analyzer_id == "audio_aasist_l_measurement":
                if (
                    result.media_type is not MediaType.AUDIO
                    or result.analyzer_version != "1.0.0"
                    or result.group != "audio"
                    or result.score is not None
                    or result.score_name is not None
                    or result.candidate_findings
                    or any(f.source_analyzer_id == result.analyzer_id for f in findings)
                ):
                    raise ValueError("invalid measurement-only AASIST-L result")
            elif result.analyzer_id not in specs:
                raise ValueError("unknown ensemble analyzer")
"""
ROLES = ("control", "manipulated", "confound_control")
SPLITS = ("calibration_observation", "holdout_demo")
MIME = {"png": "image/png", "jpg": "image/jpeg", "wav": "audio/wav", "mp4": "video/mp4"}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")


def _write_json(path: Path, value: Any) -> None:
    # Exclusive creation prevents accidental replacement of frozen evidence.
    with path.open("xb") as stream:
        stream.write(_json_bytes(value))


def _read_json(path: Path) -> Any:
    def invalid(value: str) -> None:
        raise ValueError(f"Nonfinite JSON constant: {value}")

    return json.loads(path.read_text(encoding="utf-8"), parse_constant=invalid)


def _external_directory(path: Path) -> Path:
    if not path.is_absolute():
        raise ValueError("An explicit absolute external directory is required")
    for part in (path, *path.parents):
        if part.is_symlink() or part.is_junction():
            raise ValueError("Symlink/junction output paths are not allowed")
    resolved = path.resolve()
    repo = ROOT.resolve()
    if resolved.is_relative_to(repo) or repo.is_relative_to(resolved):
        raise ValueError("Output must be outside the repository and its ancestors")
    return resolved


def _owned_path(root: Path, relative: str) -> Path:
    part = Path(relative)
    if part.is_absolute() or ".." in part.parts or ":" in relative or "\\" in relative:
        raise ValueError("Unsafe relative artifact path")
    candidate = root / part
    _external_directory(candidate)
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError("Artifact escapes workspace")
    return candidate


def _tool_version(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise RuntimeError(f"Existing runtime tool {name} is required")
    completed = subprocess.run(
        [executable, "-version"], capture_output=True, text=True, timeout=15, check=True
    )
    return completed.stdout.splitlines()[0]


def _environment() -> dict[str, Any]:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "pillow", "opencv-python-headless", "pyjpegio", "fakedetector")
        },
        "ffmpeg": _tool_version("ffmpeg"),
        "ffprobe": _tool_version("ffprobe"),
    }


def _assessment_implementation(source: str) -> dict[str, str]:
    """Verify the full frozen SHA after only exact authorized ID/wording projections."""
    current = _digest(source.encode())
    projection = source
    wording_projected = source.count(_F01_LOW_TEXT) == 1
    if wording_projected:
        projection = projection.replace(_F01_LOW_TEXT, _HISTORICAL_LOW_TEXT, 1)
    compatibility = "historical-frozen"
    if _digest(projection.encode()) != ASSESSMENT_SHA256:
        if projection.count(_AASIST_ID_GUARD) != 1:
            raise ValueError("Frozen ensemble implementation changed; this sprint forbids tuning")
        projection = projection.replace(_AASIST_ID_GUARD, _HISTORICAL_ID_GUARD, 1)
        compatibility = _AASIST_COMPATIBILITY
    projected = _digest(projection.encode())
    if projected != ASSESSMENT_SHA256:
        raise ValueError("Frozen ensemble implementation changed; this sprint forbids tuning")
    if wording_projected:
        compatibility = (
            _F01_COMPATIBILITY
            if compatibility == "historical-frozen"
            else _AASIST_F01_COMPATIBILITY
        )
    return {
        "compatibility": compatibility,
        "current_sha256_lf": current,
        "historical_sha256_lf": ASSESSMENT_SHA256,
        "scoring_projection_sha256_lf": projected,
    }


def _policy() -> dict[str, Any]:
    # read_text normalizes newlines independently of Git eol settings.
    assessment = ROOT / "src/fakedetector/lifecycle/_assessment.py"
    implementation = _assessment_implementation(assessment.read_text(encoding="utf-8"))
    raw = yaml.safe_load((ROOT / "config/config.diploma.yaml").read_text(encoding="utf-8"))
    risk = AppConfig.model_validate(raw).risk_assessment
    if (
        risk.model_id != "diploma_ensemble_v1"
        or risk.model_version != "0.1.0"
        or (risk.thresholds.low_max, risk.thresholds.medium_max) != (25, 55)
        or risk.critical_override.enabled
    ):
        raise ValueError("Diploma profile differs from the frozen policy")
    return {
        "model": "diploma_ensemble_v1@0.1.0",
        "risk_configuration": risk.model_dump(mode="json"),
        "assessment_sha256_lf": ASSESSMENT_SHA256,
        "assessment_implementation": implementation,
        "family_factors": [_family_factor(i) for i in range(4)],
        "capacities": {media.value: _media_capacity(media) for media in MediaType},
        "families": [
            {
                "family": family.key,
                "media_type": family.media_type.value,
                "members": [
                    {
                        "analyzer_id": spec.analyzer_id,
                        "weight": spec.weight,
                        "profile": spec.profile,
                    }
                    for spec in family.members
                ],
            }
            for family in _ENSEMBLE_FAMILIES
        ],
        "runtime_sha256_lf": {
            path.relative_to(ROOT).as_posix(): _digest(path.read_text(encoding="utf-8").encode())
            for path in sorted((ROOT / "src/fakedetector").rglob("*.py"))
        },
        "profile_sha256_lf": _digest(
            (ROOT / "config/config.diploma.yaml").read_text(encoding="utf-8").encode()
        ),
        "lock_sha256_lf": _digest((ROOT / "uv.lock").read_text(encoding="utf-8").encode()),
    }


@dataclass(frozen=True)
class Sample:
    sample_id: str
    pair_id: str
    media_type: str
    role: str
    split: str
    generator_version: str
    seed: int
    base: str
    transformation: str
    transformation_parameters: dict[str, Any]
    intended_target_families: tuple[str, ...]
    expected_confound: str
    file_format: str
    filename: str
    evidence_level: str = "FILE_LEVEL_E2E"


def _split(pair_id: str) -> str:
    # Predeclared pair grouping: every third base is holdout; variants never cross splits.
    return SPLITS[int(pair_id.rsplit("-", 1)[1]) % 3 == 0]


def samples() -> tuple[Sample, ...]:
    """Fixed 40-case design, independent of any analyzer result."""
    cases: list[Sample] = []

    def add(
        media: str,
        group: int,
        base: str,
        variant: str,
        role: str,
        transformation: str,
        parameters: dict[str, Any],
        families: tuple[str, ...] = (),
        confound: str = "",
        fmt: str = "",
    ) -> None:
        pair_id = f"{media}-{group:02d}"
        sample_id = f"{pair_id}-{variant}"
        format_name = fmt or {"image": "png", "audio": "wav", "video": "mp4"}[media]
        cases.append(
            Sample(
                sample_id,
                pair_id,
                media,
                role,
                _split(pair_id),
                GENERATOR_VERSION,
                {"image": 12000, "audio": 22000, "video": 32000}[media] + group,
                base,
                transformation,
                parameters,
                families,
                confound,
                format_name,
                f"corpus/{sample_id}.{format_name}",
            )
        )

    add("image", 1, "geometry", "control", "control", "none", {})
    add(
        "image",
        1,
        "geometry",
        "metadata",
        "manipulated",
        "exif_dimension_mismatch",
        {"exif_width": 1024, "exif_height": 768},
        ("image_metadata",),
    )
    add(
        "image",
        1,
        "geometry",
        "resize",
        "confound_control",
        "benign_resize",
        {"intermediate_size": 600, "output_size": 768, "filter": "bicubic"},
        ("image_local_processing",),
        "Legitimate whole-image resize",
    )
    add("image", 2, "texture", "control", "control", "none", {})
    add(
        "image",
        2,
        "texture",
        "copy",
        "manipulated",
        "copy_move",
        {"source_xy": [48, 64], "destination_xy": [460, 440], "size": 176},
        ("image_region_correspondence",),
    )
    add(
        "image",
        2,
        "texture",
        "resample",
        "manipulated",
        "local_resampling",
        {"box": [0, 0, 264, 264], "intermediate_size": 176, "filter": "bilinear"},
        ("image_local_processing",),
    )
    add(
        "image",
        2,
        "texture",
        "tiles",
        "confound_control",
        "repetitive_texture",
        {"tile_size": 128},
        ("image_region_correspondence", "image_local_processing"),
        "Ordinary repeated design, no target insertion",
    )
    add(
        "image",
        3,
        "jpeg_texture",
        "control",
        "control",
        "single_jpeg_export",
        {"quality": 90, "subsampling": 0},
        fmt="jpg",
    )
    add(
        "image",
        3,
        "jpeg_texture",
        "recompress",
        "manipulated",
        "aligned_recompression",
        {"first_quality": 40, "final_quality": 90, "subsampling": 0},
        ("image_recompression",),
        fmt="jpg",
    )
    add(
        "image",
        3,
        "jpeg_texture",
        "reexport",
        "confound_control",
        "benign_jpeg_reexport",
        {"first_quality": 90, "final_quality": 90, "subsampling": 0},
        ("image_recompression",),
        "Legitimate repeated JPEG save",
        "jpg",
    )
    add(
        "image",
        3,
        "jpeg_texture",
        "resize",
        "confound_control",
        "benign_jpeg_resize",
        {
            "first_quality": 90,
            "final_quality": 90,
            "subsampling": 0,
            "intermediate_size": 640,
            "filter": "lanczos",
        },
        ("image_recompression", "image_local_processing"),
        "Legitimate JPEG resize",
        "jpg",
    )
    add("image", 4, "low_noise", "control", "control", "none", {})
    add(
        "image",
        4,
        "low_noise",
        "local_noise",
        "manipulated",
        "local_residual_mismatch",
        {"box": [0, 0, 132, 132], "amplitude_multiplier": 4},
        ("image_local_processing",),
    )
    add(
        "image",
        4,
        "low_noise",
        "strong_noise",
        "confound_control",
        "strong_texture",
        {"amplitude_multiplier": 12},
        ("image_local_processing",),
        "Uniform strong stochastic texture, no localized edit",
    )

    for group, base in ((1, "chirp"), (2, "broadband"), (3, "envelope")):
        add("audio", group, base, "control", "control", "none", {})
    add(
        "audio",
        1,
        "chirp",
        "splice",
        "manipulated",
        "hard_splice",
        {"at_sample": 32768, "dc_step": 0.45},
        ("audio_transition", "audio_background"),
    )
    add(
        "audio",
        1,
        "chirp",
        "spectral",
        "manipulated",
        "local_spectral_change",
        {"start_sample": 24576, "stop_sample": 40960, "frequency_hz": 2700, "amplitude": 0.3},
        ("audio_transition", "audio_background"),
    )
    add(
        "audio",
        1,
        "chirp",
        "transient",
        "confound_control",
        "sharp_transient",
        {"at_sample": 32768, "length_samples": 80, "amplitude": 0.8},
        ("audio_transition",),
        "Ordinary brief percussion-like transient",
    )
    add(
        "audio",
        1,
        "chirp",
        "loop",
        "confound_control",
        "periodic_loop",
        {"period_samples": 8192},
        ("audio_repetition",),
        "Legitimate loop-like signal",
    )
    add(
        "audio",
        2,
        "broadband",
        "repeat",
        "manipulated",
        "copied_segment",
        {"source_start": 0, "destination_start": 32768, "length_samples": 16384},
        ("audio_repetition",),
    )
    add(
        "audio",
        2,
        "broadband",
        "floor",
        "manipulated",
        "background_floor_change",
        {"at_sample": 32768, "first_gain": 0.01, "second_gain": 0.2},
        ("audio_background", "audio_transition"),
    )
    add(
        "audio",
        2,
        "broadband",
        "level",
        "confound_control",
        "level_change",
        {"at_sample": 32768, "second_gain": 0.25},
        ("audio_transition", "audio_background"),
        "Legitimate gain change",
    )
    add(
        "audio",
        2,
        "broadband",
        "silence",
        "confound_control",
        "silence",
        {},
        ("audio_repetition",),
        "Digital silence; undefined measurements expected",
    )
    add(
        "audio",
        3,
        "envelope",
        "clip",
        "manipulated",
        "full_scale_clipping",
        {"gain": 8},
        ("audio_quality", "audio_transition"),
    )
    add(
        "audio",
        3,
        "envelope",
        "repeat",
        "manipulated",
        "copied_segment",
        {"source_start": 0, "destination_start": 32768, "length_samples": 16384},
        ("audio_repetition",),
    )
    add(
        "audio",
        3,
        "envelope",
        "quiet",
        "confound_control",
        "near_silence",
        {"gain": 0.0001},
        ("audio_transition", "audio_background"),
        "Near silence and PCM quantization; no synthetic-speech detection claim",
    )

    for group, base in ((1, "translation"), (2, "pan"), (3, "orbit")):
        add("video", group, base, "control", "control", "none", {})
    add(
        "video",
        1,
        "translation",
        "freeze",
        "manipulated",
        "frozen_run",
        {"start_frame": 20, "stop_frame": 55},
        ("video_quality", "video_repetition"),
    )
    add(
        "video",
        1,
        "translation",
        "distant",
        "manipulated",
        "distant_repeated_content",
        {"source_start": 0, "destination_start": 64, "length_frames": 16},
        ("video_repetition",),
    )
    add(
        "video",
        1,
        "translation",
        "cut",
        "confound_control",
        "ordinary_scene_cut",
        {"at_frame": 15},
        ("video_visual_transition",),
        "Ordinary editorial scene cut",
    )
    add(
        "video",
        2,
        "pan",
        "transition",
        "manipulated",
        "strong_visual_transition",
        {"start_frame": 15, "stop_frame": 23, "rgb": [245, 245, 245]},
        ("video_visual_transition",),
    )
    add(
        "video",
        2,
        "pan",
        "timing",
        "manipulated",
        "pts_gap",
        {"at_frame": 8, "extra_ticks": 5, "time_base": "1/8"},
        ("video_timing",),
    )
    add(
        "video",
        2,
        "pan",
        "vfr",
        "confound_control",
        "benign_variable_rate",
        {"every_frames": 8, "extra_ticks": 1, "time_base": "1/8"},
        ("video_timing",),
        "Legitimate variable frame rate",
    )
    add(
        "video",
        3,
        "orbit",
        "repeat",
        "manipulated",
        "repeated_block",
        {"source_start": 0, "destination_start": 16, "length_frames": 8},
        ("video_repetition",),
    )
    add(
        "video",
        3,
        "orbit",
        "static",
        "confound_control",
        "static_scene",
        {},
        ("video_quality", "video_repetition"),
        "Legitimate motionless scene",
    )
    add(
        "video",
        3,
        "orbit",
        "loop",
        "confound_control",
        "periodic_motion",
        {"period_frames": 8},
        ("video_quality", "video_repetition"),
        "Legitimate periodic animation",
    )
    return tuple(sorted(cases, key=lambda case: case.sample_id))


def _image_bytes(case: Sample) -> bytes:
    rng = np.random.default_rng(case.seed)
    y, x = np.indices((768, 768))
    if case.base == "geometry":
        pixels = np.stack((40 + x * 150 / 768, 50 + y * 140 / 768, 80 + (x + y) * 70 / 768), -1)
        image = Image.fromarray(pixels.astype("u1"))
        draw = ImageDraw.Draw(image)
        draw.ellipse((95, 160, 305, 380), fill=(195, 120, 70))
        draw.rectangle((440, 405, 680, 650), fill=(70, 160, 140))
    elif case.base == "low_noise":
        noise = rng.integers(-2, 3, (768, 768))
        image = Image.fromarray(np.repeat((128 + noise)[:, :, None], 3, axis=2).astype("u1"))
    else:
        fine = rng.normal(0, 18, (768, 768, 3))
        coarse = Image.fromarray(rng.integers(40, 215, (24, 24, 3), dtype="u1"))
        coarse = coarse.resize((768, 768), Image.Resampling.BICUBIC)
        values = np.asarray(coarse, dtype=float) + fine
        image = Image.fromarray(np.clip(values, 8, 247).astype("u1"))
        image = image.filter(ImageFilter.GaussianBlur(0.35))
    p, transform = case.transformation_parameters, case.transformation
    if transform == "copy_move":
        left, top = p["source_xy"]
        image.paste(
            image.crop((left, top, left + p["size"], top + p["size"])), tuple(p["destination_xy"])
        )
    elif transform == "local_resampling":
        patch = image.crop(tuple(p["box"]))
        small = patch.resize((p["intermediate_size"],) * 2, Image.Resampling.BILINEAR)
        image.paste(small.resize(patch.size, Image.Resampling.BILINEAR), (0, 0))
    elif transform == "repetitive_texture":
        tile = image.crop((0, 0, p["tile_size"], p["tile_size"]))
        for top in range(0, 768, tile.height):
            for left in range(0, 768, tile.width):
                image.paste(tile, (left, top))
    elif transform == "benign_resize":
        image = image.resize((p["intermediate_size"],) * 2, Image.Resampling.BICUBIC)
        image = image.resize((p["output_size"],) * 2, Image.Resampling.BICUBIC)
    elif transform in {"local_residual_mismatch", "strong_texture"}:
        pixels = np.asarray(image).astype(np.int16).copy()
        left, top, right, bottom = p.get("box", [0, 0, 768, 768])
        region = pixels[top:bottom, left:right]
        region[:] = 128 + (region - 128) * p["amplitude_multiplier"]
        image = Image.fromarray(pixels.astype("u1"))
    exif = Image.Exif()
    if transform == "exif_dimension_mismatch":
        exif[0xA002], exif[0xA003], exif[0x0112] = p["exif_width"], p["exif_height"], 1
    if "first_quality" in p:
        encoded = io.BytesIO()
        image.save(encoded, "JPEG", quality=p["first_quality"], subsampling=p["subsampling"])
        with Image.open(io.BytesIO(encoded.getvalue())) as first:
            image = first.copy()
        if transform == "benign_jpeg_resize":
            image = image.resize((p["intermediate_size"],) * 2, Image.Resampling.LANCZOS)
    output = io.BytesIO()
    if case.file_format == "jpg":
        image.save(
            output,
            "JPEG",
            quality=p.get("final_quality", p.get("quality")),
            subsampling=p["subsampling"],
            optimize=False,
            progressive=False,
        )
    else:
        image.save(output, "PNG", exif=exif, compress_level=9)
    return output.getvalue()


def _audio_bytes(case: Sample) -> bytes:
    rate, count = 8000, 65536
    rng = np.random.default_rng(case.seed)
    t = np.arange(count) / rate
    if case.base == "chirp":
        signal = 0.22 * np.sin(2 * np.pi * (170 * t + 23 * t * t))
        signal += 0.1 * np.sin(2 * np.pi * (431 * t + 3 * t * t))
    elif case.base == "broadband":
        signal = rng.uniform(-0.28, 0.28, count)
    else:
        envelope = (0.12 + 0.88 * np.sin(np.pi * 1.7 * t) ** 2) * (0.65 + 0.35 * np.sin(0.9 * t))
        phase = 2 * np.pi * (105 * t + 2 * np.sin(1.3 * t))
        signal = envelope * (
            0.24 * np.sin(phase) + 0.09 * np.sin(3 * phase) + 0.05 * np.sin(7 * phase)
        )
        signal += rng.normal(0, 0.003, count)
    p, transform = case.transformation_parameters, case.transformation
    if transform == "hard_splice":
        signal[p["at_sample"] :] = -signal[p["at_sample"] :] + p["dc_step"]
    elif transform == "local_spectral_change":
        start, stop = p["start_sample"], p["stop_sample"]
        signal[start:stop] = p["amplitude"] * np.sin(2 * np.pi * p["frequency_hz"] * t[start:stop])
    elif transform == "sharp_transient":
        start, length = p["at_sample"], p["length_samples"]
        signal[start : start + length] += p["amplitude"] * np.exp(-np.arange(length) / 8)
    elif transform == "periodic_loop":
        signal = np.tile(signal[: p["period_samples"]], count // p["period_samples"])
    elif transform == "copied_segment":
        a, b, n = p["source_start"], p["destination_start"], p["length_samples"]
        signal[b : b + n] = signal[a : a + n]
    elif transform == "background_floor_change":
        signal[: p["at_sample"]] *= p["first_gain"]
        signal[p["at_sample"] :] *= p["second_gain"]
    elif transform == "level_change":
        signal[p["at_sample"] :] *= p["second_gain"]
    elif transform == "silence":
        signal[:] = 0
    elif transform in {"full_scale_clipping", "near_silence"}:
        signal *= p["gain"]
    pcm = np.clip(np.rint(signal * 32768), -32768, 32767).astype("<i2")
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(pcm.tobytes())
    return output.getvalue()


def _video_frames(case: Sample) -> np.ndarray:
    rng = np.random.default_rng(case.seed)
    y, x = np.indices((180, 320))
    background = np.stack((55 + x / 3, 60 + y / 2, 100 + (x + y) / 7), -1)
    texture = rng.integers(-12, 13, (180, 320, 3))
    background = np.clip(background + texture, 0, 255).astype("u1")
    frames = []
    for index in range(80):
        frame = np.roll(background, index * 3, axis=1) if case.base == "pan" else background.copy()
        if case.base == "orbit":
            left = round(138 + 93 * np.cos(index * 0.09))
            top = round(68 + 48 * np.sin(index * 0.09))
        else:
            left, top = 12 + index * 3, 45 + index // 2
        frame[top : top + 30, left : left + 38] = (210, 65, 35)
        frames.append(frame)
    pixels = np.stack(frames)
    p, transform = case.transformation_parameters, case.transformation
    if transform == "frozen_run":
        pixels[p["start_frame"] : p["stop_frame"]] = pixels[p["start_frame"]]
    elif transform in {"distant_repeated_content", "repeated_block"}:
        a, b, n = p["source_start"], p["destination_start"], p["length_frames"]
        pixels[b : b + n] = pixels[a : a + n]
    elif transform == "ordinary_scene_cut":
        pixels[p["at_frame"] :] = 255 - pixels[p["at_frame"] :]
    elif transform == "strong_visual_transition":
        pixels[p["start_frame"] : p["stop_frame"]] = p["rgb"]
    elif transform == "static_scene":
        pixels[:] = pixels[0]
    elif transform == "periodic_motion":
        pixels = np.tile(pixels[: p["period_frames"]], (80 // p["period_frames"], 1, 1, 1))
    return pixels


def _write_video(case: Sample, target: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("FFmpeg is required")
    filters = []
    p = case.transformation_parameters
    if case.transformation == "pts_gap":
        filters = ["-vf", f"setpts=PTS+gte(N\\,{p['at_frame']})*{p['extra_ticks']}"]
    elif case.transformation == "benign_variable_rate":
        filters = ["-vf", f"setpts=PTS+floor(N/{p['every_frames']})*{p['extra_ticks']}"]
    subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-nostdin",
            "-n",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            "320x180",
            "-r",
            "8",
            "-i",
            "pipe:0",
            *filters,
            "-an",
            "-map_metadata",
            "-1",
            "-fflags",
            "+bitexact",
            "-flags:v",
            "+bitexact",
            "-c:v",
            "mpeg4",
            "-q:v",
            "2",
            "-threads",
            "1",
            "-g",
            "1",
            "-bf",
            "0",
            "-pix_fmt",
            "yuv420p",
            "-fps_mode",
            "passthrough",
            "-video_track_timescale",
            "8000",
            str(target),
        ],
        input=_video_frames(case).tobytes(),
        capture_output=True,
        timeout=60,
        check=True,
    )


def generate(output: Path) -> dict[str, Any]:
    root = _external_directory(output)
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise ValueError("Generation requires a new or empty external directory")
    policy, environment = _policy(), _environment()
    root.mkdir(parents=True, exist_ok=True)
    (root / "corpus").mkdir()
    _write_json(
        root / "freeze.json",
        {
            "baseline_head": BASELINE_HEAD,
            "policy": policy,
            "environment": environment,
            "generator_version": GENERATOR_VERSION,
            "tool_sha256_lf": _digest(Path(__file__).read_text(encoding="utf-8").encode()),
            "split_policy": (
                "pair numeric suffix divisible by 3 -> holdout_demo; others observation"
            ),
        },
    )
    rows = []
    for case in samples():
        path = root / case.filename
        if case.media_type == "video":
            _write_video(case, path)
        else:
            data = _image_bytes(case) if case.media_type == "image" else _audio_bytes(case)
            with path.open("xb") as stream:
                stream.write(data)
        data = path.read_bytes()
        rows.append(
            {
                **asdict(case),
                "intended_target_families": list(case.intended_target_families),
                "sha256": _digest(data),
                "size_bytes": len(data),
            }
        )
        print(f"generated {case.sample_id}", flush=True)
    manifest = {
        "generator_version": GENERATOR_VERSION,
        "freeze_sha256": _digest((root / "freeze.json").read_bytes()),
        "encoding": {
            "image_size": [768, 768],
            "audio_rate": 8000,
            "audio_samples": 65536,
            "audio_encoding": "mono PCM s16le",
            "video_size": [320, 180],
            "video_frames": 80,
            "video_rate": 8,
            "video_codec": "mpeg4 q2 intra",
            "video_flags": "bitexact; threads=1; metadata stripped; passthrough PTS",
        },
        "samples": rows,
    }
    _write_json(root / "manifest.json", manifest)
    (root / "manifest.sha256").write_text(_digest(_json_bytes(manifest)) + "\n", encoding="ascii")
    return manifest


def load_manifest(root: Path) -> dict[str, Any]:
    root = _external_directory(root)
    manifest_path = _owned_path(root, "manifest.json")
    digest = _digest(manifest_path.read_bytes())
    if digest != _owned_path(root, "manifest.sha256").read_text(encoding="ascii").strip():
        raise ValueError("Manifest seal mismatch")
    manifest = _read_json(manifest_path)
    freeze_path = _owned_path(root, "freeze.json")
    if _digest(freeze_path.read_bytes()) != manifest["freeze_sha256"]:
        raise ValueError("Freeze seal mismatch")
    frozen = _read_json(freeze_path)
    if frozen["policy"] != _policy() or frozen["environment"] != _environment():
        raise ValueError("Runtime, profile or tool environment changed since freeze")
    expected = json.loads(_json_bytes([asdict(case) for case in samples()]))
    actual = [
        {key: value for key, value in row.items() if key not in {"sha256", "size_bytes"}}
        for row in manifest["samples"]
    ]
    if actual != expected or manifest["generator_version"] != GENERATOR_VERSION:
        raise ValueError("Frozen sample membership, parameters or split changed")
    for row in manifest["samples"]:
        path = _owned_path(root, row["filename"])
        if path.stat().st_size != row["size_bytes"] or _digest(path.read_bytes()) != row["sha256"]:
            raise ValueError(f"Corpus integrity failure: {row['sample_id']}")
    return manifest


def _config(root: Path) -> AppConfig:
    raw = yaml.safe_load((ROOT / "config/config.diploma.yaml").read_text(encoding="utf-8"))
    # Only storage locations change. Analyzer budgets, auth and safety policies stay intact.
    raw["temporary_storage"]["root_path"] = str(root / "runtime/temp")
    raw["result"]["directory"] = str(root / "runtime/results")
    raw["logging"]["jsonl_path"] = str(root / "logs/application.jsonl")
    return AppConfig.model_validate(raw)


def _wait_result(service: Any, analysis_id: str, timeout: float) -> AnalysisResult:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            return service.get_result(analysis_id)
        except AnalysisPendingError:
            time.sleep(0.05)
    raise TimeoutError("Terminal result was not published within the harness deadline")


def extract_result(
    sample: dict[str, Any], result: AnalysisResult | None, *, failure: str | None = None
) -> dict[str, Any]:
    """Project persisted observations using the frozen production normalizers, not parsed prose."""
    risk = result.risk_assessment if result else None
    row = {
        **sample,
        "analysis_status": result.status.value if result else (failure or "not_evaluated"),
        "completeness_status": result.completeness.status.value if result else "not_assessed",
        "overall_score": risk.score if risk else None,
        "risk_level": risk.final_level.value if risk and risk.final_level else None,
        "finding_count": len(result.findings) if result else 0,
        "finding_types": sorted({f.type for f in result.findings}) if result else [],
        "limitations": list(risk.limitations) if risk else [],
        "errors": [e.code for e in result.errors] if result else [],
        "cleanup_status": result.cleanup.status.value if result and result.cleanup else None,
        "extraction_errors": [],
        "analyzers": [],
        "families": [],
    }
    if failure:
        row["errors"].append(failure)
    if result and result.file and result.file.sha256 != sample["sha256"]:
        raise ValueError("Runtime source digest differs from manifest")
    if risk and (
        risk.model_id != "diploma_ensemble_v1"
        or risk.model_version != "0.1.0"
        or risk.probability is not None
        or risk.probability_method is not None
    ):
        raise ValueError("Unexpected assessment model or probability")
    by_id = {a.analyzer_id: a for a in result.analyzers} if result else {}
    findings = tuple(result.findings) if result else ()
    media = MediaType(sample["media_type"])
    for family in _ENSEMBLE_FAMILIES:
        if family.media_type is not media:
            continue
        members = []
        for spec in family.members:
            observed = by_id.get(spec.analyzer_id)
            definition = _resolve_runtime_analyzer_definition(spec.analyzer_id)
            assert definition is not None
            try:
                response, state = _ensemble_response(spec, observed, findings)
            except ValueError as error:
                response, state = None, "extraction_error"
                row["extraction_errors"].append(f"{spec.analyzer_id}: {error}")
            if observed is None:
                state = "not_observed"
            members.append(
                {
                    "analyzer_id": spec.analyzer_id,
                    "maturity": definition.maturity.value,
                    "status": observed.status.value if observed else "not_observed",
                    "response_state": state,
                    "normalized_response": response,
                    "weight": spec.weight,
                    "effective_weighted_response": (
                        _effective_response(response, spec.weight) if response is not None else None
                    ),
                    "family_factor": None,
                    "effective_weighted_contribution": None,
                    "score_contribution": None,
                    "evidence_family": family.key,
                    "summary": observed.summary if observed else None,
                    "warnings": list(observed.warnings) if observed else [],
                    "errors": [e.code for e in observed.errors] if observed else [],
                }
            )
        usable = sorted(
            [item for item in members if item["normalized_response"] is not None],
            key=lambda item: (-item["effective_weighted_response"], item["analyzer_id"]),
        )
        remaining = 1.0
        for index, item in enumerate(usable):
            factor = _family_factor(index)
            contribution = min(remaining, item["effective_weighted_response"] * factor)
            item["family_factor"] = factor
            item["effective_weighted_contribution"] = contribution
            item["score_contribution"] = 100 * contribution / _media_capacity(media)
            remaining -= contribution
        value = _family_response([item["effective_weighted_response"] for item in usable])
        row["families"].append(
            {
                "evidence_family": family.key,
                "response": value,
                "usable_members": len(usable),
                "canonical_members": len(members),
                "score_contribution": 100 * value / _media_capacity(media),
            }
        )
        row["analyzers"].extend(members)
    if risk and risk.score is not None and not row["extraction_errors"]:
        reconstructed = _ensemble_score([f["response"] for f in row["families"]], media)
        if not math.isclose(reconstructed, risk.score, rel_tol=1e-12, abs_tol=1e-12):
            row["extraction_errors"].append(
                "Persisted score differs from extracted family responses"
            )
    return row


def evaluate(corpus: Path) -> None:
    root = _external_directory(corpus)
    manifest = load_manifest(root)
    # A run owns fresh outputs. Re-evaluation needs a new generated workspace, not overwrite.
    for directory in ("results", "runtime", "logs"):
        _owned_path(root, directory).mkdir()
    _write_json(
        root / "results/run.json",
        {
            "manifest_sha256": _digest((root / "manifest.json").read_bytes()),
            "freeze_sha256": manifest["freeze_sha256"],
            "tool_sha256_lf": _digest(Path(__file__).read_text(encoding="utf-8").encode()),
            "boundary": "AnalysisApplicationService.submit -> persisted get_result",
            "config_overrides": [
                "temporary_storage.root_path",
                "result.directory",
                "logging.jsonl_path",
            ],
        },
    )
    config = _config(root)
    # The local in-process app still constructs its normal authenticated adapters.
    # Ephemeral credentials are neither persisted nor printed, and no listener is opened.
    temporary_env = {
        config.access_channels.api.token_env_var: secrets.token_urlsafe(32),
        config.access_channels.webui.credentials_env_var: "demo:" + secrets.token_urlsafe(32),
    }
    added = [key for key in temporary_env if key not in os.environ]
    for key in added:
        os.environ[key] = temporary_env[key]
    try:
        app = create_app(config)
    finally:
        for key in added:
            del os.environ[key]
    runtime, service = app.state.runtime, app.state.application_service
    runtime.scheduler.start()
    journal = root / "results/index.jsonl"
    try:
        with journal.open("x", encoding="utf-8", newline="\n") as index:
            for sample in manifest["samples"]:
                started = time.monotonic()
                result = None
                entry = {
                    "sample_id": sample["sample_id"],
                    "analysis_id": None,
                    "result_file": None,
                    "failure": None,
                }
                try:
                    with _owned_path(root, sample["filename"]).open("rb") as stream:
                        submission = service.submit(
                            stream,
                            original_name=Path(sample["filename"]).name,
                            declared_content_type=MIME[sample["file_format"]],
                            source=SourceContext(channel=SourceChannel.API),
                        )
                    entry["analysis_id"] = submission.analysis_id
                    result = _wait_result(
                        service,
                        submission.analysis_id,
                        config.limits.processing_timeout_seconds + 180,
                    )
                except TimeoutError:
                    entry["failure"] = "harness_timeout"
                except (AnalysisApplicationError, OSError) as error:
                    entry["failure"] = type(error).__name__
                if result is not None:
                    relative = f"results/{sample['sample_id']}.json"
                    _write_json(_owned_path(root, relative), result.model_dump(mode="json"))
                    entry["result_file"] = relative
                    entry["result_sha256"] = _digest((root / relative).read_bytes())
                entry["wall_seconds"] = time.monotonic() - started
                # Persist the attempt before extraction; malformed measurements stay reviewable.
                index.write(json.dumps(entry, allow_nan=False, sort_keys=True) + "\n")
                index.flush()
                os.fsync(index.fileno())
                score = result.risk_assessment.score if result and result.risk_assessment else None
                status = result.status.value if result else entry["failure"]
                print(f"evaluated {sample['sample_id']}: {status}; score={score}", flush=True)
    finally:
        runtime.scheduler.shutdown(drain=True)
    load_manifest(root)
    _write_json(
        root / "results/complete.json",
        {
            "sample_count": len(manifest["samples"]),
            "index_sha256": _digest(journal.read_bytes()),
        },
    )


def _distribution(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "nonzero": sum(value > 0 for value in values),
        "mean": statistics.mean(values) if values else None,
        "median": statistics.median(values) if values else None,
        "max": max(values) if values else None,
    }


def pair_deltas(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pairs = []
    for pair_id in sorted({row["pair_id"] for row in rows}):
        group = [row for row in rows if row["pair_id"] == pair_id]
        controls = [row for row in group if row["role"] == "control"]
        if len(controls) != 1 or len({row["split"] for row in group}) != 1:
            raise ValueError(f"Pair must have exactly one base control and one split: {pair_id}")
        control = controls[0]
        base = {f["evidence_family"]: f["response"] for f in control["families"]}
        for variant in group:
            if variant is control:
                continue
            a, b = control["overall_score"], variant["overall_score"]
            families = {f["evidence_family"]: f["response"] for f in variant["families"]}
            differences = {key: families[key] - value for key, value in base.items()}
            pairs.append(
                {
                    "pair_id": pair_id,
                    "media_type": control["media_type"],
                    "split": control["split"],
                    "control_id": control["sample_id"],
                    "sample_id": variant["sample_id"],
                    "role": variant["role"],
                    "transformation": variant["transformation"],
                    "control_score": a,
                    "transformed_score": b,
                    "delta_score": b - a if a is not None and b is not None else None,
                    "changed_families": {
                        key: value for key, value in differences.items() if abs(value) > 1e-12
                    },
                }
            )
    return pairs


def _ratio(numerator: int, denominator: int) -> dict[str, int | float | None]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "fraction": numerator / denominator if denominator else None,
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Descriptive counts; unavailable scores never become LOW or vanish from denominators."""
    pairs = pair_deltas(rows)
    thresholds = {
        role: {
            level: sum(
                r["role"] == role and (r["risk_level"] or "unassessed") == level for r in rows
            )
            for level in ("low", "medium", "high", "unassessed")
        }
        for role in ROLES
    }
    controls = [row for row in rows if row["role"] != "manipulated"]
    manipulated = [row for row in rows if row["role"] == "manipulated"]
    transformed_pairs = [p for p in pairs if p["role"] == "manipulated"]
    defined_pairs = [p for p in transformed_pairs if p["delta_score"] is not None]
    family_rows, analyzer_rows = [], []
    for family in _ENSEMBLE_FAMILIES:
        selected = [r for r in rows if r["media_type"] == family.media_type.value]
        observations = [
            (r, f) for r in selected for f in r["families"] if f["evidence_family"] == family.key
        ]
        family_rows.append(
            {
                "evidence_family": family.key,
                "media_type": family.media_type.value,
                **_distribution([f["response"] for _, f in observations]),
                "usable_sample_count": sum(f["usable_members"] > 0 for _, f in observations),
                "activated_roles": sorted(
                    {r["role"] for r, f in observations if f["response"] > 0}
                ),
            }
        )
        for spec in family.members:
            observed = [
                a for r in selected for a in r["analyzers"] if a["analyzer_id"] == spec.analyzer_id
            ]
            states = Counter(a["response_state"] for a in observed)
            analyzer_rows.append(
                {
                    "analyzer_id": spec.analyzer_id,
                    "evidence_family": family.key,
                    "maturity": _resolve_runtime_analyzer_definition(
                        spec.analyzer_id
                    ).maturity.value,
                    "sample_count": len(observed),
                    "observed_count": sum(a["status"] != "not_observed" for a in observed),
                    "usable_count": sum(a["normalized_response"] is not None for a in observed),
                    "signal_count": states["signal"],
                    "no_signal_count": states["completed_no_signal"],
                    "insufficient_count": states["insufficient_evidence"],
                    "not_applicable_count": states["not_applicable"],
                    "error_count": states["error"],
                    "timeout_count": states["timeout"],
                    "skipped_count": states["skipped"],
                    "not_observed_count": states["not_observed"],
                    "extraction_error_count": states["extraction_error"],
                    "response_distribution": _distribution(
                        [
                            a["normalized_response"]
                            for a in observed
                            if a["normalized_response"] is not None
                        ]
                    ),
                }
            )
    return {
        "scope": "on this controlled demonstration corpus",
        "total": len(rows),
        "inventory": {
            key: dict(sorted(Counter(row[key] for row in rows).items()))
            for key in (
                "media_type",
                "role",
                "transformation",
                "split",
                "evidence_level",
                "analysis_status",
                "completeness_status",
            )
        },
        "threshold_matrix": thresholds,
        "elevated_control_responses": [
            r["sample_id"] for r in controls if r["risk_level"] in {"medium", "high"}
        ],
        "missed_weak_controlled_transformations": [
            r["sample_id"] for r in manipulated if r["risk_level"] == "low"
        ],
        "unassessed_samples": [r["sample_id"] for r in rows if r["overall_score"] is None],
        "extraction_errors": {
            r["sample_id"]: r["extraction_errors"] for r in rows if r["extraction_errors"]
        },
        "metrics": {
            "demo_elevated_control_rate_gt25": _ratio(
                sum(r["overall_score"] is not None and r["overall_score"] > 25 for r in controls),
                len(controls),
            ),
            "demo_elevated_control_rate_gt55": _ratio(
                sum(r["overall_score"] is not None and r["overall_score"] > 55 for r in controls),
                len(controls),
            ),
            "demo_manipulated_rate_gt25": _ratio(
                sum(
                    r["overall_score"] is not None and r["overall_score"] > 25 for r in manipulated
                ),
                len(manipulated),
            ),
            "demo_manipulated_rate_gt55": _ratio(
                sum(
                    r["overall_score"] is not None and r["overall_score"] > 55 for r in manipulated
                ),
                len(manipulated),
            ),
            "pairwise_score_increase_rate": _ratio(
                sum(p["delta_score"] > 1e-12 for p in defined_pairs), len(defined_pairs)
            ),
            "pair_count": len(transformed_pairs),
            "assessed_pair_count": len(defined_pairs),
            "median_pair_delta": statistics.median(p["delta_score"] for p in defined_pairs)
            if defined_pairs
            else None,
        },
        "families": family_rows,
        "analyzers": analyzer_rows,
        "pairs": pairs,
    }


def _cell(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.6f}"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    return str(value)


def _markdown_table(headers: list[str], values: list[list[Any]]) -> str:
    def line(row: list[Any]) -> str:
        return (
            "| "
            + " | ".join(_cell(value).replace("|", "\\|").replace("\n", " ") for value in row)
            + " |"
        )

    return "\n".join([line(headers), line(["---"] * len(headers)), *(line(row) for row in values)])


def _report_markdown(rows: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines = [
        "# Контролируемый демонстрационный корпус — результаты",
        "",
        "Это воспроизводимый инженерный эксперимент, "
        "не внешняя валидация или оценка точности в реальном мире.",
        "CONTROL: генератор не вносил целевую манипуляцию; MANIPULATED: известное преобразование; "
        "CONFOUND CONTROL: доброкачественный контент/обработка с возможным похожим откликом.",
        "",
        "Модель `diploma_ensemble_v1@0.1.0` заморожена до прогона. "
        "LOW ≤25; MEDIUM 25<score≤55; HIGH >55. probability=null. Калибровка не выполнялась.",
        "",
        "Нулевое семейство без пригодных измерений — арифметический ноль, "
        "не свидетельство отсутствия аномалии. "
        "В распределение семейств входят такие нули; число пригодных наблюдений указано отдельно. "
        "Распределение анализатора включает только определённые отклики. "
        "Доли используют все файлы своей роли; unassessed указан отдельно. "
        "Парная доля использует только пары с двумя оценками; "
        "числа всех и оценённых пар сохранены.",
    ]
    for split in ("all", *SPLITS):
        section = summary["all"] if split == "all" else summary["splits"][split]
        selected = rows if split == "all" else [r for r in rows if r["split"] == split]
        lines += ["", f"## {split}", "", "### A. Состав корпуса", ""]
        lines.append(
            _markdown_table(
                ["Признак", "Значение", "Количество"],
                [
                    [key, value, count]
                    for key, counts in section["inventory"].items()
                    for value, count in counts.items()
                ],
            )
        )
        lines += ["", "### B. Результаты файлов", ""]
        sample_rows = []
        for row in selected:
            strongest = sorted(
                row["families"], key=lambda f: (-f["response"], f["evidence_family"])
            )
            notable = {
                a["analyzer_id"]: a["normalized_response"]
                for a in row["analyzers"]
                if a["response_state"] == "signal"
            }
            sample_rows.append(
                [
                    row["sample_id"],
                    row["role"],
                    row["transformation"],
                    row["analysis_status"],
                    row["completeness_status"],
                    row["overall_score"],
                    row["risk_level"],
                    strongest[0]["evidence_family"]
                    if strongest and strongest[0]["response"] > 0
                    else None,
                    notable,
                ]
            )
        lines.append(
            _markdown_table(
                [
                    "sample_id",
                    "role",
                    "transformation",
                    "status",
                    "completeness",
                    "score",
                    "level",
                    "strongest family",
                    "analyzer responses",
                ],
                sample_rows,
            )
        )
        lines += ["", "### C. Парные сравнения (включая доброкачественные варианты)", ""]
        lines.append(
            _markdown_table(
                [
                    "control",
                    "variant",
                    "role",
                    "control score",
                    "variant score",
                    "delta",
                    "family deltas",
                ],
                [
                    [
                        p["control_id"],
                        p["sample_id"],
                        p["role"],
                        p["control_score"],
                        p["transformed_score"],
                        p["delta_score"],
                        p["changed_families"],
                    ]
                    for p in section["pairs"]
                ],
            )
        )
        lines += ["", "### D/E/H. Контроли, преобразования и текущие пороги", ""]
        lines.append(
            _markdown_table(
                ["role", "LOW", "MEDIUM", "HIGH", "unassessed"],
                [
                    [role, *(counts[level] for level in ("low", "medium", "high", "unassessed"))]
                    for role, counts in section["threshold_matrix"].items()
                ],
            )
        )
        lines += [
            "",
            "**Elevated control responses:** "
            + (", ".join(section["elevated_control_responses"]) or "нет")
            + ".",
            "Это не автоматическая классификация algorithmic false positive; "
            "причины требуют контекста.",
            "",
            "**Missed/weak controlled transformations:** "
            + (", ".join(section["missed_weak_controlled_transformations"]) or "нет")
            + ".",
            "",
            "**Unassessed:** " + (", ".join(section["unassessed_samples"]) or "нет") + ".",
            "",
            "### F. Семейства",
            "",
        ]
        lines.append(
            _markdown_table(
                ["family", "count", "usable", "nonzero", "mean", "median", "max", "roles"],
                [
                    [
                        f["evidence_family"],
                        f["count"],
                        f["usable_sample_count"],
                        f["nonzero"],
                        f["mean"],
                        f["median"],
                        f["max"],
                        f["activated_roles"],
                    ]
                    for f in section["families"]
                ],
            )
        )
        lines += ["", "### G. Анализаторы", ""]
        lines.append(
            _markdown_table(
                [
                    "analyzer",
                    "maturity",
                    "usable",
                    "signal",
                    "no signal",
                    "insufficient",
                    "N/A",
                    "error",
                    "timeout",
                    "skipped",
                    "not observed",
                    "extraction error",
                    "distribution",
                ],
                [
                    [
                        a["analyzer_id"],
                        a["maturity"],
                        a["usable_count"],
                        a["signal_count"],
                        a["no_signal_count"],
                        a["insufficient_count"],
                        a["not_applicable_count"],
                        a["error_count"],
                        a["timeout_count"],
                        a["skipped_count"],
                        a["not_observed_count"],
                        a["extraction_error_count"],
                        a["response_distribution"],
                    ]
                    for a in section["analyzers"]
                ],
            )
        )
        lines += ["", "### Описательные показатели только на этом корпусе", ""]
        lines.append(
            _markdown_table(
                ["Показатель", "Значение"],
                [[key, value] for key, value in section["metrics"].items()],
            )
        )
    return "\n".join(lines) + "\n"


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("A report table must have a defined row schema")
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False, allow_nan=False)
                    if isinstance(value, (dict, list, tuple))
                    else value
                    for key, value in row.items()
                }
            )


def report(corpus: Path) -> dict[str, Any]:
    root = _external_directory(corpus)
    manifest = load_manifest(root)
    known_ids = {row["sample_id"] for row in manifest["samples"]}
    entries = {}
    journal = _owned_path(root, "results/index.jsonl")
    if journal.exists():
        run = _read_json(_owned_path(root, "results/run.json"))
        if run["manifest_sha256"] != _digest((root / "manifest.json").read_bytes()):
            raise ValueError("Evaluation was run against another manifest")
        complete = _owned_path(root, "results/complete.json")
        if complete.exists() and _read_json(complete)["index_sha256"] != _digest(
            journal.read_bytes()
        ):
            raise ValueError("Evaluation journal seal mismatch")
        for line in journal.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            sample_id = entry["sample_id"]
            if sample_id not in known_ids or sample_id in entries:
                raise ValueError("Unknown or duplicate evaluation entry")
            entries[sample_id] = entry
    rows = []
    for sample in manifest["samples"]:
        entry = entries.get(sample["sample_id"], {})
        result = None
        if entry.get("result_file"):
            path = _owned_path(root, entry["result_file"])
            if _digest(path.read_bytes()) != entry["result_sha256"]:
                raise ValueError("Persisted result seal mismatch")
            result = AnalysisResult.model_validate(_read_json(path))
            if result.analysis_id != entry["analysis_id"]:
                raise ValueError("Result identity mismatch")
        row = extract_result(sample, result, failure=entry.get("failure"))
        row["wall_seconds"] = entry.get("wall_seconds")
        rows.append(row)
    summary = {
        "generator_version": GENERATOR_VERSION,
        "model": "diploma_ensemble_v1@0.1.0",
        "manifest_sha256": _digest((root / "manifest.json").read_bytes()),
        "all": aggregate(rows),
        "splits": {split: aggregate([r for r in rows if r["split"] == split]) for split in SPLITS},
    }
    tables = _owned_path(root, "tables")
    tables.mkdir(exist_ok=True)
    # Derived tables may be regenerated. Frozen media, manifest and results are never overwritten.
    for filename, data in (("summary.json", summary), ("samples.json", rows)):
        _owned_path(root, f"tables/{filename}").write_bytes(_json_bytes(data))
    flat_rows = [
        {key: value for key, value in row.items() if key not in {"families", "analyzers"}}
        for row in rows
    ]
    _write_csv(_owned_path(root, "tables/score-by-sample.csv"), flat_rows)
    for key, name in (
        ("families", "family-responses.csv"),
        ("analyzers", "analyzer-responses.csv"),
    ):
        flattened = [
            {
                "sample_id": r["sample_id"],
                "pair_id": r["pair_id"],
                "media_type": r["media_type"],
                "role": r["role"],
                "split": r["split"],
                **item,
            }
            for r in rows
            for item in r[key]
        ]
        _write_csv(_owned_path(root, f"tables/{name}"), flattened)
    _write_csv(_owned_path(root, "tables/pair-deltas.csv"), summary["all"]["pairs"])
    _owned_path(root, "tables/report.md").write_text(
        _report_markdown(rows, summary), encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("generate").add_argument("--output", type=Path, required=True)
    for name in ("evaluate", "report"):
        sub.add_parser(name).add_argument("--corpus", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "generate":
        generate(args.output)
    elif args.command == "evaluate":
        evaluate(args.corpus)
    else:
        summary = report(args.corpus)
        print(
            json.dumps(
                {
                    "total": summary["all"]["total"],
                    "threshold_matrix": summary["all"]["threshold_matrix"],
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
