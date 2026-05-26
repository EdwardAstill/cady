from __future__ import annotations

import argparse
from pathlib import Path

from cady import Model, circle, line, rectangle

GALLERY_DIR = Path(__file__).resolve().parents[1] / "gallery"


def build_model() -> Model:
    outline = rectangle((0.0, 0.0), (1.0, 0.6))
    hole = circle((0.5, 0.3), 0.12)
    profile = outline.with_hole(hole)

    model = Model("production_plate")
    front = model.drawing("front")
    front.layer("PLATE", color=7).add(outline).add(hole)
    front.layer("SECTION", color=8).hatch(profile, pattern="ANSI31", scale=0.025)
    front.layer("CENTER", color=3, linetype="CENTER").add(line((0.5, 0.05), (0.5, 0.55)))
    front.add_text("PRODUCTION PLATE", at=(0.02, 0.02), height=0.03, layer="TEXT")
    front.linear_dimension((0.0, 0.0), (1.0, 0.0), offset=-0.08, layer="DIMENSIONS")
    front.linear_dimension((1.0, 0.0), (1.0, 0.6), offset=-0.08, layer="DIMENSIONS")
    front.diameter_dimension((0.5, 0.3), 0.12, layer="DIMENSIONS")
    front.radius_dimension((0.5, 0.3), 0.12, angle=1.5707963267948966, layer="DIMENSIONS")

    symbol = front.block("PIN_MARK", base=(0, 0))
    symbol.layer("SYMBOL", color=2).add(circle((0, 0), 0.025))
    front.insert("PIN_MARK", at=(0.5, 0.3), layer="SYMBOL")
    front.insert("PIN_MARK", at=(0.82, 0.3), layer="SYMBOL", rotation=90)

    model.part("plate").add(profile.extrude("+z", 0.04))
    return model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=GALLERY_DIR)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    build_model().write_dxf(args.out / "production_plate.dxf")


if __name__ == "__main__":
    main()
