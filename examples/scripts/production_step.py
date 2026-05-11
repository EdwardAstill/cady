from __future__ import annotations

import argparse
from pathlib import Path

from cad import Model, prism

GALLERY_DIR = Path(__file__).resolve().parents[1] / "gallery"


def build_model() -> Model:
    model = Model("production_plate")
    model.part("plate").add(prism((0.0, 0.0, 0.0), (1.0, 0.6, 0.04)))
    model.part("pin").add(prism((0.45, 0.25, 0.04), (0.1, 0.1, 0.08)))
    return model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=GALLERY_DIR)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    build_model().write_step(args.out / "production_plate.step")


if __name__ == "__main__":
    main()
