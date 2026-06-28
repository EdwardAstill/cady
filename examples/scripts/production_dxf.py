from __future__ import annotations

import argparse
from pathlib import Path

from example_geometry import GALLERY_DIR, production_drawing

from cady import Drawing2
from cady.files import dxf


def build_drawing() -> Drawing2:
    return production_drawing()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=GALLERY_DIR)
    parser.add_argument("--tolerance", type=float, default=1e-3)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    dxf.write(build_drawing(), args.out / "production_plate.dxf", tolerance=args.tolerance)


if __name__ == "__main__":
    main()
