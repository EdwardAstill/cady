from __future__ import annotations

import argparse
from pathlib import Path

from example_geometry import GALLERY_DIR, plate_document, scene_for_target, scene_summary

from cady import Drawing2D, Part
from cady.files import dxf, stl


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=GALLERY_DIR)
    parser.add_argument("--tolerance", type=float, default=1e-3)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    document = plate_document()
    drawing = document.get("drawing", "front")
    part = document.get("part", "plate")
    if not isinstance(drawing, Drawing2D) or not isinstance(part, Part):
        raise TypeError("plate document has unexpected contents")

    scene = scene_for_target(part, name="plate_scene")
    (args.out / "visualise_plate_scene.txt").write_text(scene_summary(scene), encoding="utf-8")
    dxf.write(drawing, args.out / "visualise_plate.dxf", tolerance=args.tolerance)
    stl.write(part, args.out / "visualise_plate.stl", tolerance=args.tolerance)
    print(scene_summary(scene).rstrip())


if __name__ == "__main__":
    main()
