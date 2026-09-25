"""Predeclared aligned R3C histories; never acquires or opens a holdout."""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from pathlib import Path

from PIL import Image

from .jpeg_corpus import Case, decoded, encode
from .jpeg_dq_rule import CalibrationSource
from .jpeg_pilot import external


def generate(source: CalibrationSource, output: Path, ordinal: int) -> list[dict[str, object]]:
    source.original.verify()
    source.master.verify()
    source.terms.verify()
    output = external(output)
    output.mkdir(parents=True, exist_ok=True)
    workflows = (
        ("single", ((40, 75, 95)[ordinal % 3],)),
        ("single90", (90,)),
        ("aligned40to90", (40, 90)),
        ("aligned90to40", (90, 40)),
        ("same75", (75, 75)),
        ("close85to90", (85, 90)),
        ("repeat", (40, 60, 80, 90)),
    )
    with Image.open(source.master.path) as opened:
        if opened.format != "PNG" or opened.mode != "RGB":
            raise ValueError("bounded developed RGB PNG required")
        if max(opened.size) > 1280 or opened.width * opened.height > 1_000_000:
            raise ValueError("bounded master required")
        opened.load()
        master: Image.Image = opened
        if ordinal % 10 == 0:
            master = master.convert("L")
        sampling = (ordinal // 3) % 3
        progressive = ordinal % 5 == 0
        results: list[dict[str, object]] = []
        for name, qualities in workflows:
            image = master.copy()
            chain: list[dict[str, object]] = []
            parent = source.master.sha256
            if image.mode == "L":
                digest = hashlib.sha256(image.tobytes()).hexdigest()
                chain.append({"operation": "Pillow RGB to L", "input": parent, "output": digest})
                parent = digest
            first_tables = {}
            for index, quality in enumerate(qualities):
                final_step = index == len(qualities) - 1
                data = encode(image, quality, sampling, progressive if final_step else False)
                digest = hashlib.sha256(data).hexdigest()
                image, tables = decoded(data)
                chain.append(
                    {
                        "operation": "JPEG",
                        "input": parent,
                        "output": digest,
                        "quality": quality,
                        "subsampling": sampling,
                        "progressive": progressive if final_step else False,
                        "dqt": tables,
                    }
                )
                parent = digest
                if index == 0 and len(qualities) > 1:
                    first_tables = tables
            if name == "same75" and first_tables != tables:
                raise ValueError("same-DQT invariant")
            case_id = source.source_group + "-" + name
            path = output / (case_id + ".jpg")
            if path.exists() and path.read_bytes() != data:
                raise ValueError("refuse different derivative")
            path.write_bytes(data)
            case = Case(
                case_id,
                source.source_group,
                source.partition,
                source.content,
                "single" if len(qualities) == 1 else "recompressed",
                name,
                image.width,
                image.height,
                image.mode,
                digest,
                len(data),
                qualities[0] if len(qualities) > 1 else None,
                qualities[-1],
                sampling,
                progressive,
                1,
                (0, 0),
                first_tables,
                tables,
            )
            results.append({"case": asdict(case), "path": str(path), "chain": chain})
    return results
