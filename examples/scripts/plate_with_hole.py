from __future__ import annotations

import argparse
from pathlib import Path

from cady import DxfDrawing, StlMesh, circle, rectangle

GALLERY_DIR = Path(__file__).resolve().parents[1] / "gallery"


def build_plate():
    outline = rectangle((0.0, 0.0), (1.0, 0.6))
    hole = circle((0.5, 0.3), 0.12)
    profile = outline.with_hole(hole)
    return outline, hole, profile.extrude(axis="+z", distance=0.04)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=GALLERY_DIR)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    outline, hole, solid = build_plate()
    drawing = DxfDrawing()
    drawing.layer("PLATE", 7).add(outline).add(hole)
    drawing.add_text("PLATE", at=(0.02, 0.02), height=0.03, layer="TEXT")
    drawing.write(args.out / "plate.dxf")
    StlMesh(tolerance=1e-3).add(solid).write(args.out / "plate.stl")


if __name__ == "__main__":
    main()
