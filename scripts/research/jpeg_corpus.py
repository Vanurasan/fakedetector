"""Deterministic, self-generated M2-R2 media; no downloaded source material."""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, JpegImagePlugin


@dataclass(frozen=True)
class Case:
    case_id: str
    source_group: str
    partition: str
    content: str
    history: str
    variant: str
    width: int
    height: int
    mode: str
    sha256: str
    size_bytes: int
    first_quality: int | None
    final_quality: int
    subsampling: int
    progressive: bool
    orientation: int
    shift: tuple[int, int]
    first_tables: dict[int, list[int]]
    final_tables: dict[int, list[int]]


def source_image(kind: str, seed: int, size: tuple[int, int] = (199, 167)) -> Image.Image:
    """Six/eight content families are challenges, not independent natural photographs."""
    w, h = size
    y, x = np.indices((h, w))
    rng = np.random.default_rng(seed)
    if kind == "noise":
        values = rng.integers(0, 256, (h, w, 3), dtype=np.uint8)
    elif kind == "smooth":
        values = np.stack(
            (
                128 + 75 * np.sin(x / 19) * np.cos(y / 23),
                128 + 75 * np.sin((x + y) / 27),
                128 + 75 * np.cos((x - y) / 21),
            ),
            axis=-1,
        ).astype(np.uint8)
    elif kind == "periodic":
        values = np.repeat((((x // 8 + y // 8) % 2) * 210 + 20)[..., None], 3, axis=2)
    elif kind == "saturated":
        values = np.stack(
            ((x % 31 < 16) * 255, (y % 23 < 12) * 255, ((x + y) % 19 < 10) * 255), axis=-1
        )
    elif kind == "flat":
        values = np.full((h, w, 3), 128)
    elif kind == "sparse":
        values = np.full((h, w, 3), 128)
        values[h // 2 : h // 2 + 8, w // 2 : w // 2 + 8] = 230
    else:
        values = np.full((h, w, 3), 245)
    image = Image.fromarray(values.astype(np.uint8))
    draw = ImageDraw.Draw(image)
    if kind == "text":
        # Own geometric seven-segment-like glyphs; no external font provenance.
        for top in range(5, h - 12, 16):
            for left in range(5, w - 8, 12):
                draw.rectangle((left, top, left + 6, top + 10), outline=(15, 15, 15))
                draw.line((left, top + 5, left + 6, top + 5), fill=(15, 15, 15))
    if kind == "lines":
        for offset in range(-h, w, 11):
            draw.line((offset, 0, offset + h, h), fill=(20, 80, 170), width=2)
    return image


def encode(
    image: Image.Image,
    quality: int,
    subsampling: int,
    progressive: bool = False,
    orientation: int = 1,
    tables: dict[int, list[int]] | None = None,
) -> bytes:
    output = io.BytesIO()
    exif = Image.Exif()
    exif[274] = orientation
    if tables is None:
        image.save(
            output,
            "JPEG",
            quality=quality,
            subsampling=subsampling,
            progressive=progressive,
            exif=exif,
        )
    else:
        image.save(
            output,
            "JPEG",
            qtables=tables,
            subsampling=subsampling,
            progressive=progressive,
            exif=exif,
        )
    return output.getvalue()


def decoded(data: bytes) -> tuple[Image.Image, dict[int, list[int]]]:
    # Corpus construction only; measurement JPEG decoding belongs to preprocessing.
    with Image.open(io.BytesIO(data)) as image:
        assert isinstance(image, JpegImagePlugin.JpegImageFile)
        tables = {int(k): list(v) for k, v in image.quantization.items()}
        return image.copy(), tables


def generate(root: Path) -> list[Case]:
    root.mkdir(parents=True, exist_ok=False)
    cases: list[Case] = []
    kinds = ("smooth", "noise", "periodic", "text", "lines", "saturated", "flat", "sparse")
    for index, kind in enumerate(kinds):
        source = source_image(kind, 1200 + index)
        group = f"generated-{kind}-120{index}"
        source.save(root / f"{group}.png")
        # Fixed before measurements. Content families differ, so holdout is exploratory only.
        partition = "exploratory_holdout" if kind in ("lines", "saturated") else "exploratory"
        variants: list[tuple[str, int | None, int, int, bool, int, int, int]] = []
        for quality in (20, 40, 75, 90, 95, 100):
            variants.append(("single", None, quality, 2, False, 1, 0, 0))
        variants.append(("source_shift_single", None, 100, 2, False, 1, 3, 5))
        for first_step, final_step in ((40, 90), (90, 40), (75, 75), (74, 75), (99, 100)):
            variants.append(("aligned", first_step, final_step, 2, False, 1, 0, 0))
        for subsampling in (0, 1, 2):
            for progressive in (False, True):
                variants.append(("format", 40, 90, subsampling, progressive, 1, 0, 0))
        for variant in (
            "gray",
            "gray_rgb",
            "repeat",
            "resize",
            "nearest",
            "bicubic",
            "sharpen",
            "collage",
            "patch_inside",
            "patch_edge",
            "custom_same",
            "custom_near",
            "custom_multiple",
        ):
            variants.append((variant, 40, 90, 2, False, 1, 0, 0))
        if kind in ("smooth", "noise", "periodic"):
            for variant in ("large_collage", "panorama_inside", "panorama_outside"):
                variants.append((variant, 40, 95, 2, False, 1, 0, 0))
        if kind in ("smooth", "periodic"):
            for first_step, final_step in ((40, 90), (90, 40)):
                for dy in range(8):
                    for dx in range(8):
                        variants.append(("shift", first_step, final_step, 2, False, 1, dx, dy))
            for orientation in range(1, 9):
                variants.append(("exif", 40, 90, 2, False, orientation, 3, 5))
            variants.append(("invalid_exif", None, 75, 2, False, 9, 0, 0))
        for ordinal, (variant, first, final, sub, prog, orientation, dx, dy) in enumerate(variants):
            image = source.copy()
            if variant == "large_collage":
                image = image.resize((1200, 800), Image.Resampling.BICUBIC)
            if variant.startswith("panorama"):
                image = image.resize((4096, 256), Image.Resampling.BICUBIC)
            if variant in ("gray", "gray_rgb"):
                image = image.convert("L")
                if variant == "gray_rgb":
                    image = image.convert("RGB")
            first_tables: dict[int, list[int]] = {}
            final_tables = None
            if first is not None:
                if variant.startswith("custom"):
                    first_tables = {0: [8] * 64, 1: [8] * 64}
                data = encode(image, first, sub, tables=first_tables or None)
                image, first_tables = decoded(data)
            if dx or dy:
                image = image.crop((dx, dy, image.width, image.height))
            if variant == "repeat":
                for quality in (60, 80):
                    image, _ = decoded(encode(image, quality, sub))
            if variant in ("resize", "nearest", "bicubic"):
                method = (
                    Image.Resampling.NEAREST if variant == "nearest" else Image.Resampling.BICUBIC
                )
                image = image.resize((image.width // 2, image.height // 2), method)
                image = image.resize(source.size, method)
            if variant == "sharpen":
                image = image.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
            if variant in (
                "collage",
                "large_collage",
                "patch_inside",
                "patch_edge",
                "panorama_inside",
                "panorama_outside",
            ):
                # Exact permutation of an already decoded first JPEG; no interpolation.
                shifted = Image.fromarray(np.roll(np.asarray(image), (5, 3), axis=(0, 1)))
                if variant in ("collage", "large_collage"):
                    box = (image.width // 2, 0, image.width, image.height)
                elif variant.startswith("panorama"):
                    left = 100 if variant == "panorama_inside" else 600
                    box = (left, 100, left + 16, 116)
                else:
                    left, top = (70, 70) if variant == "patch_inside" else (0, 0)
                    box = (left, top, left + 8, top + 8)
                image.paste(shifted.crop(box), box)
            if variant.startswith("custom"):
                step = {"custom_same": 8, "custom_near": 9, "custom_multiple": 16}[variant]
                final_tables = {0: [step] * 64, 1: [step] * 64}
            data = encode(image, final, sub, prog, orientation, final_tables)
            _, actual_tables = decoded(data)
            case_id = f"{group}-{ordinal:03d}-{variant}"
            (root / f"{case_id}.jpg").write_bytes(data)
            cases.append(
                Case(
                    case_id,
                    group,
                    partition,
                    kind,
                    "single" if first is None else "recompressed",
                    variant,
                    image.width,
                    image.height,
                    image.mode,
                    hashlib.sha256(data).hexdigest(),
                    len(data),
                    first,
                    final,
                    sub,
                    prog,
                    orientation,
                    (dx, dy),
                    first_tables,
                    actual_tables,
                )
            )
    for size, kind in (
        *(
            (size, "noise")
            for size in (
                (7, 7),
                (8, 8),
                (9, 9),
                (66, 67),
                (67, 66),
                (67, 67),
                (1024, 67),
                (1536, 1536),
                (2048, 2048),
            )
        ),
        ((2048, 2048), "flat"),
    ):
        image = source_image(kind, 1300, size).convert("L")
        data = encode(image, 75, 0)
        _, tables = decoded(data)
        case_id = f"support-{size[0]}x{size[1]}-{kind}"
        (root / f"{case_id}.jpg").write_bytes(data)
        cases.append(
            Case(
                case_id,
                "generated-support-1300" if kind == "noise" else "generated-flat-1206",
                "resource_boundary",
                kind,
                "single",
                "support",
                *size,
                "L",
                hashlib.sha256(data).hexdigest(),
                len(data),
                None,
                75,
                0,
                False,
                1,
                (0, 0),
                {},
                tables,
            )
        )
    return cases
