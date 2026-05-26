from __future__ import annotations

import argparse
from pathlib import Path

from cady import Model, circle, rectangle

GALLERY_DIR = Path(__file__).resolve().parents[1] / "gallery"


def build_model() -> Model:
    outline = rectangle((0.0, 0.0), (1.0, 0.6))
    hole = circle((0.5, 0.3), 0.12)
    profile = outline.with_hole(hole)

    model = Model("model_plate")
    drawing = model.drawing("front")
    drawing.layer("PLATE", 7).add(outline).add(hole)
    drawing.add_text("PLATE", at=(0.02, 0.02), height=0.03, layer="TEXT")
    model.part("plate").add(profile.extrude(axis="+z", distance=0.04))
    return model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=GALLERY_DIR)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    model = build_model()
    model.write_dxf(args.out / "model_plate.dxf")
    model.write_stl(args.out / "model_plate.stl")


if __name__ == "__main__":
    main()
