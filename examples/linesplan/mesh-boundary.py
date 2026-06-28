"""Read mirrored DXF line geometry as a mesh and show its boundary.

Usage:
    PYTHONPATH=src .venv/bin/python examples/linesplan/mesh-boundary.py --no-view
    PYTHONPATH=src .venv/bin/python examples/linesplan/mesh-boundary.py
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from cady import Camera, DirectionalLight, DisplayStyle, Mesh3, Scene, Wireframe3
from cady.files import dxf
from cady.operations.arrays import PointArray3

ROOT = Path(__file__).resolve().parents[2]
LINESPLAN_DXF = ROOT / "examples" / "inputs" / "linesplan_9m.dxf"
VIEW_ASPECT = 900.0 / 700.0
FIT_PADDING = 1.08
MESH_STYLE = DisplayStyle(color=(0.46, 0.52, 0.50), opacity=0.9)
BOUNDARY_STYLES = (
    DisplayStyle(color=(1.0, 0.08, 0.58), render_mode="wireframe", line_width=2.0),
    DisplayStyle(color=(0.0, 0.42, 1.0), render_mode="wireframe", line_width=2.0),
)
LIGHT = DirectionalLight(direction=(0.0, -1.0, -1.0), intensity=1.2)

Point3 = tuple[float, float, float]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read mirrored DXF line geometry as a mesh and show its boundary.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=LINESPLAN_DXF,
        help="DXF file to read.",
    )
    parser.add_argument(
        "--mirror-origin",
        "--plane-origin",
        nargs=3,
        type=float,
        default=(0.0, 0.0, 0.0),
        metavar=("X", "Y", "Z"),
        help="Point on the mirror plane.",
    )
    parser.add_argument(
        "--mirror-normal",
        "--plane-normal",
        nargs=3,
        type=float,
        default=(0.0, 1.0, 0.0),
        metavar=("X", "Y", "Z"),
        help="Mirror plane normal.",
    )
    parser.add_argument(
        "--no-view",
        action="store_true",
        help="Print summaries without opening a VisPy window.",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=1e-3,
        help="Geometry tolerance used when converting the wireframe to a mesh.",
    )
    args = parser.parse_args()

    mirror_origin = _point3(args.mirror_origin)
    mirror_normal = _point3(args.mirror_normal)
    wireframe = dxf.read_wireframe(args.input).mirror(mirror_origin, mirror_normal)
    mesh = wireframe.to_mesh(tolerance=args.tolerance)
    boundary_loops = mesh.boundary_loops
    boundaries = _meshes_from_boundary_loops(boundary_loops)

    print("cady mesh boundary demo")
    print(f"input: {args.input}")
    print(f"mirror origin: {_format_point(mirror_origin)}")
    print(f"mirror normal: {_format_point(mirror_normal)}")
    print_wireframe_summary("source wireframe", wireframe)
    print_mesh_summary("mesh", mesh)
    print(
        "  boundary loops: "
        f"{len(boundary_loops)} ({_format_loop_edge_counts(boundary_loops)})"
    )

    if args.no_view:
        print("VisPy viewer skipped.")
        return

    from cady.view import view_scene

    view_scene(build_scene(mesh, boundaries), title="linesplan 9m - mesh boundary")


def build_scene(mesh: Mesh3, boundaries: tuple[Mesh3, ...]) -> Scene:
    lower, upper = mesh.bounds()
    lower = _point_tuple(lower)
    upper = _point_tuple(upper)
    centre = _bounds_centre(lower, upper)
    camera = _fit_profile_camera(lower, upper)
    scene = Scene(name="linesplan_9m_mirror_mesh").add(mesh, name="mesh", style=MESH_STYLE)
    for index, boundary in enumerate(boundaries, start=1):
        scene = scene.add(
            boundary,
            name=f"boundary_loop_{index}",
            style=_boundary_style(index - 1),
        )
    return scene.with_camera(camera, name="profile").with_light(LIGHT).with_metadata(
        target=_format_point(centre),
    )


def print_mesh_summary(label: str, mesh: Mesh3) -> None:
    lower, upper = mesh.bounds()
    print(
        f"{label}: {len(mesh.vertices)} vertices, {len(mesh.edges)} edges, "
        f"{len(mesh.faces)} faces, "
        f"bounds={_format_point(_point_tuple(lower))} "
        f"to {_format_point(_point_tuple(upper))}"
    )


def print_wireframe_summary(label: str, wireframe: Wireframe3) -> None:
    lower, upper = wireframe.bounds()
    print(
        f"{label}: {len(wireframe.vertices)} vertices, {len(wireframe.edges)} edges, "
        f"bounds={_format_point(_point_tuple(lower))} "
        f"to {_format_point(_point_tuple(upper))}"
    )


def _meshes_from_boundary_loops(
    loops: tuple[PointArray3, ...],
) -> tuple[Mesh3, ...]:
    return tuple(_mesh_from_boundary_loop(loop) for loop in loops)


def _mesh_from_boundary_loop(loop: PointArray3) -> Mesh3:
    points = [(float(point[0]), float(point[1]), float(point[2])) for point in loop]
    if len(points) >= 2 and points[0] == points[-1]:
        points = points[:-1]
    edges = tuple((index, (index + 1) % len(points)) for index in range(len(points)))
    return Mesh3(tuple(points), (), edges)


def _boundary_style(index: int) -> DisplayStyle:
    return BOUNDARY_STYLES[index % len(BOUNDARY_STYLES)]


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


def _point3(value: Sequence[float]) -> Point3:
    if len(value) != 3:
        raise ValueError("point values must contain exactly three coordinates")
    x, y, z = value
    return (float(x), float(y), float(z))


def _point_tuple(value: Point3) -> Point3:
    return value


def _format_point(point: Point3) -> str:
    return f"({point[0]:g}, {point[1]:g}, {point[2]:g})"


def _format_loop_edge_counts(loops: tuple[PointArray3, ...]) -> str:
    counts = [max(len(loop) - 1, 0) for loop in loops]
    return ", ".join(f"{count} edges" for count in counts)


if __name__ == "__main__":
    main()
