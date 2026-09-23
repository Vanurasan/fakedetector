"""Run: uv run python -m scripts.research.jpeg_calibration --output ABSOLUTE_PATH.

This CLI generates controlled cases; jpeg_pilot supplies admitted external cases
to the same measurement path. Production services own intake validation,
measurement preprocessing, numeric access and temporary artifact cleanup.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
import time
import tracemalloc
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import cast

import numpy as np
import yaml
from PIL import Image

from fakedetector._generated_artifact_budget import _GeneratedArtifactBudget
from fakedetector.analyzers._models import (
    AnalyzerArtifactInput,
    AnalyzerRequest,
    _AnalyzerFileFacts,
    _ReadOnlyAnalyzerInput,
)
from fakedetector.config._snapshot import _ConfigSnapshot
from fakedetector.config.models import AppConfig, ImagePreprocessingConfig
from fakedetector.domain import (
    ImageTechnicalParameters,
    InputFileDescriptor,
    MediaType,
    SourceContext,
)
from fakedetector.intake.service import ControlledInput
from fakedetector.intake.temporary_input import LocalTemporaryInputOwner, PreparedSourceRef
from fakedetector.intake.validation import FileValidator
from fakedetector.lifecycle.artifacts import WorkspaceArtifactRegistry
from fakedetector.preprocessing._errors import PreprocessingError
from fakedetector.preprocessing._models import OriginalImageFacts
from fakedetector.preprocessing._requirements import (
    ForensicCapability,
    ForensicResourcePolicy,
    PreprocessingRequirements,
)
from fakedetector.preprocessing._service import ImagePreprocessor, PreprocessingRequest

from .jpeg_corpus import Case, generate
from .jpeg_measurements import DQMeasurement, GridWindow, measure_dq, measure_grid, native_raster


@dataclass(frozen=True)
class Measurement:
    case: Case
    dq: tuple[DQMeasurement, ...]
    grid: tuple[GridWindow, ...]
    grid_state: str
    preprocess_seconds: float
    dq_seconds: float
    grid_seconds: float
    numeric_bytes: int
    measurement_peak_traced_bytes: int | None


class AdmissionError(ValueError):
    """Factual intake rejection, never a negative forensic measurement."""


def measure(
    case: Case,
    root: Path,
    config: AppConfig,
    *,
    input_path: Path | None = None,
    dq_only: bool = False,
) -> Measurement:
    path = input_path if input_path is not None else root / "corpus" / f"{case.case_id}.jpg"
    analysis_id = hashlib.sha256(case.case_id.encode()).hexdigest()[:32]
    owner = LocalTemporaryInputOwner(root / "workspace")
    temporary = owner.create(analysis_id)
    try:
        with path.open("rb") as stream:
            facts = owner.ingest(temporary, stream, config.limits.max_file_size_mb.image * 2**20)
        if facts.sha256 != case.sha256 or facts.size_bytes != case.size_bytes:
            raise AdmissionError("input_identity_changed")
        now = datetime.now(UTC)
        validation = FileValidator(config=config, temporary_input_owner=owner).validate(
            ControlledInput(
                analysis_id=analysis_id,
                registered_at=now,
                source=SourceContext(channel="api"),
                input_file=InputFileDescriptor(
                    original_name=path.name,
                    declared_content_type=None,
                    size_bytes=facts.size_bytes,
                    received_at=now,
                ),
                sha256=facts.sha256,
                owned_source=temporary,
            )
        )
        if not validation.accepted:
            raise AdmissionError(validation.errors[0].code)
        descriptor = validation.validated_file
        assert descriptor is not None
        technical = descriptor.technical_parameters
        if not isinstance(technical, ImageTechnicalParameters) or technical.format != "JPEG":
            raise AdmissionError("research_requires_jpeg")
        if (technical.width, technical.height, technical.color_mode) != (
            case.width,
            case.height,
            case.mode,
        ):
            raise AdmissionError("manifest_geometry_mismatch")
        accepted = owner.transfer(temporary)
    except BaseException:
        owner.cleanup(temporary)
        raise
    registry = WorkspaceArtifactRegistry(root / "workspace" / analysis_id)
    started = time.perf_counter()

    # Existing operation ceilings remain in preprocessing; this is only a deadline.
    def remaining() -> float:
        value = 60 - (time.perf_counter() - started)
        if value <= 0:
            raise TimeoutError("research case deadline")
        return value

    try:
        prepared = ImagePreprocessor(config.preprocessing.image).prepare(
            PreprocessingRequest(
                analysis_id=analysis_id,
                validated_file=descriptor,
                source_file_ref=PreparedSourceRef(accepted),
                artifact_registry=registry,
                artifact_budget=_GeneratedArtifactBudget(
                    _ConfigSnapshot.capture(config), MediaType.IMAGE
                ),
            ),
            PreprocessingRequirements(forensic=frozenset({ForensicCapability.JPEG_COEFFICIENTS})),
            remaining_timeout_seconds=remaining,
        )
        preprocess_seconds = time.perf_counter() - started
        request = AnalyzerRequest(
            analysis_id=analysis_id,
            media_type=MediaType.IMAGE,
            file_facts=_AnalyzerFileFacts.from_validated_file(descriptor),
            source=_ReadOnlyAnalyzerInput(path),
            settings=ImagePreprocessingConfig(),
            timeout_seconds=remaining(),
            metadata=prepared.metadata,
            artifacts=tuple(
                AnalyzerArtifactInput(
                    artifact_id=a.artifact_id,
                    artifact_type=a.artifact_type,
                    format=a.format,
                    content=_ReadOnlyAnalyzerInput(
                        registry.with_local_artifact_path(a.artifact_ref, lambda p: p)
                    ),
                )
                for a in prepared.artifacts
            ),
        )
        manifest = request.forensic
        assert manifest is not None
        original = next(
            r.facts for r in manifest.representations if isinstance(r.facts, OriginalImageFacts)
        )
        # Production manifest validates shape, source identity, selector and provenance binding.
        numeric_bytes = sum(
            n.nbytes for r in manifest.representations for n in r.numeric_artifacts()
        )
        resource_probe = case.width * case.height >= 2**20
        if resource_probe:
            tracemalloc.start()
        dq_start = time.perf_counter()
        dq = measure_dq(request)
        remaining()
        dq_seconds = time.perf_counter() - dq_start
        grid_start = time.perf_counter()
        grid: tuple[GridWindow, ...] = ()
        state = "not_applicable"
        if (
            not dq_only
            and original.jpeg
            and original.source_mode in ("L", "RGB")
            and original.coordinates.orientation
        ):
            width, height = original.coordinates.oriented_size
            ForensicResourcePolicy().check_raster(width, height)
            artifact = next(a for a in request.artifacts if a.artifact_type == "normalized_image")
            with artifact.content.open_for_read() as png_stream, Image.open(png_stream) as image:
                if image.size != (width, height) or image.mode not in ("L", "RGB"):
                    raise ValueError("normalized raster geometry/mode mismatch")
                raster = np.asarray(image)
            raster = native_raster(raster, original.coordinates.orientation)
            if original.source_mode == "L" and raster.ndim == 3:
                if not (
                    np.array_equal(raster[..., 0], raster[..., 1])
                    and np.array_equal(raster[..., 0], raster[..., 2])
                ):
                    raise ValueError("grayscale normalization changed channels")
                raster = raster[..., 0]
            grid = measure_grid(raster, check_time=remaining)
            state = "measured" if grid else "not_applicable_small"
            if grid and all(w.x.n == 0 and w.y.n == 0 for w in grid):
                state = "insufficient_votes"
        grid_seconds = time.perf_counter() - grid_start
        peak = tracemalloc.get_traced_memory()[1] if resource_probe else None
        return Measurement(
            case, dq, grid, state, preprocess_seconds, dq_seconds, grid_seconds, numeric_bytes, peak
        )
    finally:
        if tracemalloc.is_tracing():
            tracemalloc.stop()
        cleanup = registry.cleanup_once()
        if not cleanup.completed:
            raise RuntimeError("research artifact cleanup incomplete")
        accepted.cleanup()


def quantiles(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"n": 0}
    q = np.quantile(values, (0, 0.25, 0.5, 0.75, 1))
    return dict(
        zip(("min", "p25", "median", "p75", "max"), map(float, q), strict=True), n=len(values)
    )


def aggregate(results: list[Measurement]) -> dict[str, object]:
    distributions: dict[str, list[float]] = defaultdict(list)
    correlations: dict[str, list[tuple[float, float]]] = defaultdict(list)
    states: Counter[str] = Counter()
    grid_summary: dict[str, Counter[str]] = defaultdict(Counter)
    for result in results:
        c = result.case
        flags = [w for w in result.grid if w.flag]
        phases = {(w.x.block_phase, w.y.block_phase) for w in flags}
        shifted = bool(phases - {(0, 0)})
        states[f"grid/{result.grid_state}"] += 1
        strata = (
            f"history={c.history}",
            f"variant={c.variant}",
            f"content={c.content}",
            f"subsampling={c.subsampling}",
            f"quality={c.final_quality}",
            f"mode={c.mode}",
            f"partition={c.partition}",
        )
        for stratum in strata:
            grid_summary[stratum].update(
                cases=1,
                any_flag=int(bool(flags)),
                shifted_flag=int(shifted),
                multiple_phases=int(len(phases) > 1),
                no_windows=int(not result.grid),
            )
        for dq in result.dq:
            h = dq.histogram
            states[f"dq/{h.state}"] += 1
            mode = f"c={dq.component},u={dq.u},v={dq.v},q2={dq.q2}"
            for stratum in strata:
                for metric in (
                    "n",
                    "span",
                    "occupied",
                    "zero_fraction",
                    "empty_fraction",
                    "frequency",
                    "amplitude",
                ):
                    value = getattr(h, metric)
                    if value is not None:
                        distributions[f"{stratum}/{mode}/{metric}"].append(float(value))
            if h.amplitude is not None:
                distributions[f"grid_shifted={shifted}/{mode}/amplitude"].append(h.amplitude)
                correlations[mode].append((h.amplitude, float(shifted)))
        for window in result.grid:
            for axis in ("x", "y"):
                a = getattr(window, axis)
                for metric in ("n", "m", "maximum_fraction", "ell"):
                    value = getattr(a, metric)
                    if value is not None:
                        distributions[f"grid/{c.variant}/{axis}/{metric}"].append(float(value))
    association = {}
    for mode, pairs in correlations.items():
        paired_values = np.asarray(pairs)
        coefficient = None
        if len(pairs) > 2 and np.std(paired_values[:, 0]) > 0 and np.std(paired_values[:, 1]) > 0:
            coefficient = float(np.corrcoef(paired_values.T)[0, 1])
        association[mode] = {"n": len(pairs), "pearson_exploratory_only": coefficient}
    # Interval intersection is descriptive overlap, never classifier accuracy.
    overlap = {}
    for key, values in distributions.items():
        if key.startswith("history=single/"):
            other = distributions.get(key.replace("history=single/", "history=recompressed/"))
            if other:
                lo, hi = max(min(values), min(other)), min(max(values), max(other))
                overlap[key] = {
                    "single_n": len(values),
                    "recompressed_n": len(other),
                    "ranges_intersect": lo <= hi,
                    "intersection": [lo, hi] if lo <= hi else None,
                }
    return {
        "case_count": len(results),
        "source_groups": len({r.case.source_group for r in results}),
        "states": dict(states),
        "grid_by_stratum": dict(grid_summary),
        "distributions": {k: quantiles(v) for k, v in sorted(distributions.items())},
        "single_recompressed_range_overlap": overlap,
        "dq_grid_association": association,
        "caveat": "No DQ flag, no forensic score; derivative/window counts are not independent n.",
        "runtime_seconds": {
            name: quantiles([getattr(r, name) for r in results])
            for name in ("preprocess_seconds", "dq_seconds", "grid_seconds")
        },
        "largest_numeric_bytes": max(r.numeric_bytes for r in results),
        "resource_probes": [
            asdict(r) for r in results if r.measurement_peak_traced_bytes is not None
        ],
    }


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = cast(Path, args.output).resolve()
    repo = Path(__file__).resolve().parents[2]
    if root == repo or root.is_relative_to(repo):
        raise ValueError("calibration media/results must be outside repository")
    root.mkdir(parents=True, exist_ok=False)
    config = AppConfig.model_validate(
        yaml.safe_load((repo / "config/config.example.yaml").read_text(encoding="utf-8"))
    )
    cases = generate(root / "corpus")
    write_json(root / "inventory.json", [asdict(c) for c in cases])
    write_json(
        root / "provenance.json",
        {
            "baseline_sha": "0fc37897aa67dbe08468d52ff9e9999b39301fad",
            "python": sys.version,
            "platform": platform.platform(),
            "versions": {name: version(name) for name in ("numpy", "pillow", "pyjpegio")},
            "source_fingerprints": {
                str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((repo / "scripts/research").glob("*.py"))
            },
            "source_rights": "Own geometric/PRNG generators in jpeg_corpus.py; no external media.",
            "holdout": "Fixed content groups before measurement; exploratory, no population FPR.",
        },
    )
    results = []
    rejections = []
    with (root / "measurements.jsonl").open("w", encoding="utf-8") as stream:
        for i, case in enumerate(cases):
            try:
                result = measure(case, root, config)
            except PreprocessingError as error:
                if error.kind != "resource_limit":
                    raise
                # Preserve admission failures as failures, never as negative measurements.
                rejections.append({"case": asdict(case), "kind": error.kind, "phase": error.phase})
                continue
            results.append(result)
            stream.write(json.dumps(asdict(result), allow_nan=False) + "\n")
            stream.flush()
            if i % 25 == 0:
                print(f"Measured {i + 1}/{len(cases)}", flush=True)
    write_json(root / "aggregate.json", aggregate(results))
    write_json(root / "rejections.json", rejections)
    with (root / "dq.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                "case_id",
                "source_group",
                "component",
                "u",
                "v",
                "q2",
                "excluded",
                "n",
                "min",
                "max",
                "span",
                "occupied",
                "zero",
                "empty",
                "frequency",
                "amplitude",
                "state",
            )
        )
        for r in results:
            for d in r.dq:
                writer.writerow(
                    (
                        r.case.case_id,
                        r.case.source_group,
                        d.component,
                        d.u,
                        d.v,
                        d.q2,
                        d.excluded_blocks,
                        *asdict(d.histogram).values(),
                    )
                )
    sizes = {p.name: p.stat().st_size for p in root.iterdir() if p.is_file()}
    write_json(root / "output_sizes.json", sizes)
    print(json.dumps({"cases": len(results), "output": str(root), "bytes": sizes}), flush=True)


if __name__ == "__main__":
    main()
