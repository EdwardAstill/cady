"""Read a DXF as a Wireframe3D and visualise it.

Usage:
    PYTHONPATH=src .venv/bin/python examples/linesplan/wireframe.py --no-view
    PYTHONPATH=src .venv/bin/python examples/linesplan/wireframe.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from cady import Camera, DirectionalLight, DisplayStyle, Scene, Wireframe3D
from cady.files import dxf

ROOT = Path(__file__).resolve().parents[2]
LINESPLAN_DXF = ROOT / "examples" / "inputs" / "linesplan_9m.dxf"
VIEW_ASPECT = 900.0 / 700.0
FIT_PADDING = 1.08
WIRE_STYLE = DisplayStyle(color=(0.05, 0.23, 0.55), render_mode="wireframe")
LIGHT = DirectionalLight(direction=(0.0, -1.0, -1.0), intensity=1.2)

Point3 = tuple[float, float, float]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read a DXF as a Wireframe3D and visualise it.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=LINESPLAN_DXF,
        help="DXF file to read.",
    )
    parser.add_argument(
        "--no-view",
        action="store_true",
        help="Print summaries without opening a VisPy window.",
    )
    args = parser.parse_args()

    wireframe = dxf.read_wireframe(args.input)

    print("cady wireframe demo")
    print(f"input: {args.input}")
    print_wireframe_summary("wireframe", wireframe)

    if args.no_view:
        print("VisPy viewer skipped.")
        return

    from cady.visualisation import view_scene

    view_scene(build_scene(wireframe), title="linesplan 9m - wireframe")


def build_scene(wireframe: Wireframe3D) -> Scene:
    lower, upper = wireframe.bounds()
    lower = _point_tuple(lower)
    upper = _point_tuple(upper)
    centre = _bounds_centre(lower, upper)
    camera = _fit_profile_camera(lower, upper)
    return (
        Scene(name="linesplan_9m_wireframe")
        .add(wireframe, name="wireframe", style=WIRE_STYLE)
        .with_camera(camera, name="profile")
        .with_light(LIGHT)
        .with_metadata(target=_format_point(centre))
    )


def print_wireframe_summary(label: str, wireframe: Wireframe3D) -> None:
    lower, upper = wireframe.bounds()
    print(
        f"{label}: {len(wireframe.vertices)} vertices, {len(wireframe.edges)} edges, "
        f"bounds={_format_point(_point_tuple(lower))} "
        f"to {_format_point(_point_tuple(upper))}"
    )


def _fit_profile_camera(lower: Point3, upper: Point3) -> Camera:
    centre = _bounds_centre(lower, upper)
    span = (upper[0] - lower[0], upper[1] - lower[1], upper[2] - lower[2])
    profile_scale = max(span[2], span[0] / VIEW_ASPECT, 1.0) * FIT_PADDING
    distance = max(span) * 1.5 or 1.0
    return Camera.orthographic(
        position=(centre[0], centre[1] - distance, centre[2]),
        target=centre,
        scale=profile_scale,
    )


def _bounds_centre(lower: Point3, upper: Point3) -> Point3:
    return (
        (lower[0] + upper[0]) / 2.0,
        (lower[1] + upper[1]) / 2.0,
        (lower[2] + upper[2]) / 2.0,
    )


def _point_tuple(value: object) -> Point3:
    point = value.tuple() if hasattr(value, "tuple") else value
    x, y, z = point
    return (float(x), float(y), float(z))


def _format_point(point: Point3) -> str:
    return f"({point[0]:g}, {point[1]:g}, {point[2]:g})"


if __name__ == "__main__":
    main()
