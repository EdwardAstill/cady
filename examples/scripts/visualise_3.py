"""Open the 3D examples in the VisPy scene viewer.

Usage:
    PYTHONPATH=src .venv/bin/python examples/scripts/visualise_3.py
    PYTHONPATH=src .venv/bin/python examples/scripts/visualise_3.py --shape plate
    PYTHONPATH=src .venv/bin/python examples/scripts/visualise_3.py --shape assembly
    PYTHONPATH=src .venv/bin/python examples/scripts/visualise_3.py --shape sphere
"""

from __future__ import annotations

import argparse

from example_geometry import (
    plate_part,
    production_assembly,
    scene_for_target,
    scene_summary,
)

from cady import Assembly, Body3, Part
from cady.view import view_scene


def build_plate() -> Part:
    return plate_part()


def build_assembly() -> Assembly:
    return production_assembly()


SHAPES: dict[str, str] = {
    "plate": "Extruded plate with hole",
    "box": "Plain box",
    "sphere": "Sphere",
    "assembly": "Two-part assembly (plate + pin)",
    "all": "All shapes, one after another",
}


def _target_for_shape(shape: str) -> object:
    if shape == "plate":
        return build_plate()
    if shape == "box":
        return Body3.box(width=1.0, depth=0.6, height=0.4)
    if shape == "sphere":
        return Body3.sphere(radius=0.5, center=(0.5, 0.3, 0.5))
    if shape == "assembly":
        return build_assembly()
    raise ValueError(f"unknown shape: {shape}")


def _describe_target(label: str, target: object, *, tolerance: float) -> object:
    key = label.lower().replace(" ", "_")
    scene = scene_for_target(target, name=key)
    print()
    print(label)
    print(scene_summary(scene).rstrip())
    print(_mesh_summary(target, tolerance=tolerance))
    return scene


def _mesh_summary(target: object, *, tolerance: float) -> str:
    meshable = target
    if isinstance(target, Part | Assembly | Body3):
        mesh = target.to_mesh(tolerance=tolerance)
    else:
        to_mesh = getattr(meshable, "to_mesh", None)
        if not callable(to_mesh):
            return "mesh: unavailable"
        mesh = to_mesh(tolerance=tolerance)

    lower, upper = mesh.bounds()
    lower_point = _point_tuple(lower)
    upper_point = _point_tuple(upper)
    return (
        f"mesh: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces, "
        f"bounds={lower_point} to {upper_point}"
    )


def _point_tuple(value: object) -> tuple[float, float, float]:
    point = value.tuple() if hasattr(value, "tuple") else value
    x, y, z = point
    return (float(x), float(y), float(z))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build an interactive 3D viewer for the example geometry",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--shape",
        choices=list(SHAPES),
        default="all",
        help="Which shape to view (default: all)",
    )
    parser.add_argument("--tolerance", type=float, default=1e-3)
    parser.add_argument(
        "--no-view",
        action="store_true",
        help="Print scene and mesh summaries without opening a VisPy window",
    )
    args = parser.parse_args()

    tolerance = args.tolerance
    choice = args.shape

    print("cady 3D scene demo")
    print(f"  tolerance: {tolerance}")
    print(f"  shape: {choice}")

    selected = ("plate", "box", "sphere", "assembly") if choice == "all" else (choice,)
    scenes: list[object] = []
    for shape in selected:
        scene = _describe_target(
            SHAPES[shape],
            _target_for_shape(shape),
            tolerance=tolerance,
        )
        scenes.append(scene)

    if args.no_view:
        print("\nVisPy viewer skipped.")
        print("Done.")
        return

    for scene in scenes:
        view_scene(scene, tolerance=tolerance)

    print("\nDone.")


if __name__ == "__main__":
    main()
