"""Small deterministic JPEG histories from admitted, offline-developed RGB masters."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, ImageChops

from .jpeg_corpus import Case, decoded, encode
from .jpeg_pilot import Record, Source, Transform, external


def _jpeg_step(
    image: Image.Image,
    quality: int,
    subsampling: int,
    progressive: bool,
    parent: str,
    chain: list[Transform],
) -> tuple[bytes, str]:
    data = encode(image, quality, subsampling, progressive)
    digest = hashlib.sha256(data).hexdigest()
    chain.append(
        Transform(
            operation="jpeg_encode",
            input_sha256=parent,
            output_sha256=digest,
            settings={
                "quality": quality,
                "subsampling": subsampling,
                "progressive": progressive,
                "orientation": 1,
                "encoder": "Pillow",
                "input_decode": "Pillow decoded RGB pixels",
            },
        )
    )
    return data, digest


def derivatives(source: Source, output: Path, *, extended: bool, ordinal: int) -> list[Record]:
    """One single JPEG per source; seven paired histories only on a bounded subset."""
    source.verify()
    if source.dataset != "rawpixls" or source.master is None:
        raise ValueError("controlled derivatives require an admitted RAW master")
    output = external(output)
    output.mkdir(parents=True, exist_ok=True)
    with Image.open(source.master.path) as master:
        if master.format not in ("PNG", "TIFF") or master.mode != "RGB":
            raise ValueError("lossless RGB research master required")
        if max(master.size) > 1280 or master.width * master.height > 1_000_000:
            raise ValueError("master exceeds bounded pilot design")
        master.load()
        variants = ["single"]
        if extended:
            variants += [
                "single90",
                "aligned",
                "same_dqt",
                "repeat",
                "shift",
                "resize",
                "phase_patch",
            ]
        records = []
        for variant in variants:
            image = master.copy()
            first = None if variant.startswith("single") else (75 if variant == "same_dqt" else 40)
            final = (
                (40, 75, 95)[ordinal % 3]
                if variant == "single"
                else (75 if variant == "same_dqt" else 90)
            )
            subsampling = (ordinal // 3) % 3
            progressive = ordinal % 5 == 0
            chain: list[Transform] = []
            parent = source.master.sha256
            first_tables = {}
            shift = (0, 0)

            if first is not None:
                data, parent = _jpeg_step(image, first, subsampling, False, parent, chain)
                image, first_tables = decoded(data)
            if variant == "repeat":
                for quality in (60, 80):
                    data, parent = _jpeg_step(image, quality, subsampling, False, parent, chain)
                    image, _ = decoded(data)
            if variant in ("shift", "resize", "phase_patch"):
                if variant == "shift":
                    box = (3, 5, image.width, image.height)
                    image = image.crop(box)
                    shift = (3, 5)
                    settings = {"box": list(box)}
                elif variant == "resize":
                    size = (image.width * 3 // 4, image.height * 3 // 4)
                    image = image.resize(size, Image.Resampling.BICUBIC)
                    settings = {"size": list(size), "filter": "BICUBIC"}
                else:
                    box = (image.width // 2, 0, image.width, image.height)
                    image.paste(ImageChops.offset(image, 3, 5).crop(box), box)
                    settings = {"box": list(box), "offset": [3, 5], "wrap": True}
                # Hash the exact intermediate RGB buffer, not a fictitious encoded file.
                digest = hashlib.sha256(image.tobytes()).hexdigest()
                chain.append(
                    Transform(
                        operation=variant,
                        input_sha256=parent,
                        output_sha256=digest,
                        settings={**settings, "hash_kind": "RGB8_C_order_pixels"},
                    )
                )
                parent = digest
            data, digest = _jpeg_step(image, final, subsampling, progressive, parent, chain)
            _, final_tables = decoded(data)
            if variant == "same_dqt" and first_tables != final_tables:
                raise ValueError("same-DQT control did not preserve tables")
            case_id = f"{source.source_id}-{variant}"
            path = output / f"{case_id}.jpg"
            if path.exists() and path.read_bytes() != data:
                raise ValueError("refuse to replace different derivative")
            path.write_bytes(data)
            case = Case(
                case_id,
                source.source_group,
                source.partition,
                "unclassified_real_scene",
                "single" if first is None else "recompressed",
                variant,
                image.width,
                image.height,
                image.mode,
                digest,
                len(data),
                first,
                final,
                subsampling,
                progressive,
                1,
                shift,
                first_tables,
                final_tables,
            )
            records.append(
                Record(
                    source_id=source.source_id,
                    path=path,
                    case=case,
                    transforms=tuple(chain),
                )
            )
        return records
