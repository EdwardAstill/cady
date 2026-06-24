from __future__ import annotations

import argparse
from pathlib import Path

from example_geometry import GALLERY_DIR, production_assembly

from cady import Assembly
from cady.files import step


def build_assembly() -> Assembly:
    return production_assembly()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=GALLERY_DIR)
    parser.add_argument("--tolerance", type=float, default=1e-3)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    step.write(build_assembly(), args.out / "production_plate.step", tolerance=args.tolerance)


if __name__ == "__main__":
    main()
