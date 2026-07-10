from __future__ import annotations

import argparse
from pathlib import Path

from example_geometry import OUTPUT_DIR, plate_document

from cady import Document, Drawing2, Part
from cady.files import dxf, stl


def build_document() -> Document:
    return plate_document(name="model_plate")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--tolerance", type=float, default=1e-3)
    parser.add_argument("--ascii-stl", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    document = build_document()
    drawing = document.get("drawing", "front")
    part = document.get("part", "plate")
    if not isinstance(drawing, Drawing2) or not isinstance(part, Part):
        raise TypeError("model_plate document has unexpected contents")

    dxf.write(drawing, args.out / "model_plate.dxf", tolerance=args.tolerance)
    stl.write(
        part,
        args.out / "model_plate.stl",
        ascii=args.ascii_stl,
        tolerance=args.tolerance,
    )


if __name__ == "__main__":
    main()
