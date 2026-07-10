from __future__ import annotations

import argparse
from pathlib import Path

from example_geometry import OUTPUT_DIR, plate_example

from cady.files import dxf, stl


def build_plate():
    return plate_example()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--tolerance", type=float, default=1e-3)
    parser.add_argument("--ascii-stl", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    plate = build_plate()
    dxf.write(plate.drawing, args.out / "plate.dxf", tolerance=args.tolerance)
    stl.write(
        plate.part,
        args.out / "plate.stl",
        ascii=args.ascii_stl,
        tolerance=args.tolerance,
    )


if __name__ == "__main__":
    main()
