"""Mirror a DXF wireframe about a plane and close the gap.

Reads the wireframe, mirrors it, then caps the open boundary using
edge-based planar triangulation. Produces a closed Mesh3D.

Usage:
    PYTHONPATH=src .venv/bin/python examples/linesplan/close-mirror-mesh.py --no-view
    PYTHONPATH=src .venv/bin/python examples/linesplan/close-mirror-mesh.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from cady import Camera, DirectionalLight, DisplayStyle, Mesh3D, Scene, Vec3, Wireframe3D
from cady.files import dxf

ROOT = Path(__file__).resolve().parents[2]
LINESPLAN_DXF = ROOT / "examples" / "inputs" / "linesplan_9m.dxf"
VIEW_ASPECT = 900.0 / 700.0
FIT_PADDING = 1.08
SOURCE_STYLE = DisplayStyle(color=(0.05, 0.23, 0.55), render_mode="wireframe")
MIRROR_STYLE = DisplayStyle(color=(0.72, 0.25, 0.12), render_mode="wireframe")
CLOSED_STYLE = DisplayStyle(color=(0.45, 0.45, 0.45))
LIGHT = DirectionalLight(direction=(0.0, -1.0, -1.0), intensity=1.2)
PLANE_STYLE = DisplayStyle(color=(0.9, 0.9, 0.3))
BOUNDARY_STYLE = DisplayStyle(color=(1.0, 0.3, 0.1), render_mode="wireframe")

Point3 = tuple[float, float, float]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mirror a DXF wireframe about a plane and close the gap.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=LINESPLAN_DXF,
        help="DXF file to read.",
    )
    parser.add_argument(
        "--mirror-origin",
        nargs=3,
        type=float,
        default=(0.0, 0.0, 0.0),
        metavar=("X", "Y", "Z"),
        help="Point on the mirror plane (default: origin, centreline at Y=0).",
    )
    parser.add_argument(
        "--mirror-normal",
        nargs=3,
        type=float,
        default=(0.0, 1.0, 0.0),
        metavar=("X", "Y", "Z"),
        help="Mirror plane normal (default: Y).",
    )
    parser.add_argument(
        "--close-origin",
        nargs=3,
        type=float,
        default=(0.0, 0.0, 0.0),
        metavar=("X", "Y", "Z"),
        help="Point on the closing plane (default: origin).",
    )
    parser.add_argument(
        "--close-normal",
        nargs=3,
        type=float,
        default=(0.0, 0.0, 1.0),
        metavar=("X", "Y", "Z"),
        help="Closing plane normal (default: Z, XY plane).",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=1e-3,
        help="Tolerance for triangulation and planar checks.",
    )
    parser.add_argument(
        "--max-distance",
        type=float,
        default=1.0,
        help="Max distance from plane for boundary edges to be projected (metres).",
    )
    parser.add_argument(
        "--no-view",
        action="store_true",
        help="Print summaries without opening a VisPy window.",
    )
    args = parser.parse_args()

    mirror_origin = _point3(args.mirror_origin)
    mirror_normal = _point3(args.mirror_normal)
    close_origin = _point3(args.close_origin)
    close_normal = _point3(args.close_normal)
    source = dxf.read_wireframe(args.input)
    mirrored = source.mirror(mirror_origin, mirror_normal)

    print("cady close-mirror-wireframe demo")
    print(f"input: {args.input}")
    print(f"mirror origin: {_format_point(mirror_origin)}")
    print(f"mirror normal: {_format_point(mirror_normal)}")
    print(f"close origin:  {_format_point(close_origin)}")
    print(f"close normal:  {_format_point(close_normal)}")
    print(f"tolerance: {args.tolerance}g")
    print(f"max_distance: {args.max_distance}g")
    print_wireframe_summary("source", source)
    print_wireframe_summary("mirrored", mirrored)

    # Project boundary edges to the closing plane and create wall faces
    closed = mirrored.close_to_plane(
        close_origin,
        close_normal,
        tolerance=args.tolerance,
        max_distance=args.max_distance,
    )
    print_mesh_summary("closed", closed)

    # Highlight boundary edges within max_distance of the close plane
    boundary = _boundary_near_plane(mirrored, close_origin, close_normal, args.max_distance)
    # Subtract boundary from mirrored so the highlighted edges stand out
    boundary_edge_set = set(boundary.edges)
    mirrored_body = Wireframe3D(
        mirrored.vertices,
        tuple(e for e in mirrored.edges if e not in boundary_edge_set),
    )
    print(f"  boundary edges near plane: {len(boundary.edges)}")

    if args.no_view:
        print("VisPy viewer skipped.")
        return

    from cady.visualisation import view_scene

    view_scene(
        build_scene(source, mirrored_body, closed, boundary, close_origin, close_normal),
        title="linesplan 9m - closed mirror",
    )


def _boundary_near_plane(
    wf: Wireframe3D,
    origin: Point3,
    normal: Point3,
    max_distance: float,
) -> Wireframe3D:
    """Return edges with both endpoints within max_distance of the plane."""
    near_edges: list[tuple[int, int]] = []
    for a, b in wf.edges:
        da = abs(
            (wf.vertices[a].x - origin[0]) * normal[0]
            + (wf.vertices[a].y - origin[1]) * normal[1]
            + (wf.vertices[a].z - origin[2]) * normal[2]
        )
        db = abs(
            (wf.vertices[b].x - origin[0]) * normal[0]
            + (wf.vertices[b].y - origin[1]) * normal[1]
            + (wf.vertices[b].z - origin[2]) * normal[2]
        )
        if da <= max_distance and db <= max_distance:
            near_edges.append((a, b))
    return Wireframe3D(wf.vertices, tuple(near_edges))


def build_scene(
    source: Wireframe3D,
    mirrored: Wireframe3D,
    closed: Mesh3D,
    boundary: Wireframe3D,
    close_origin: Point3,
    close_normal: Point3,
) -> Scene:
    lower, upper = _combined_bounds((source, mirrored, closed))
    centre = _bounds_centre(lower, upper)
    camera = _fit_profile_camera(lower, upper)
    plane = _build_plane_mesh(lower, upper, close_origin, close_normal)
    return (
        Scene(name="linesplan_9m_closed")
        .add(source, name="source", style=SOURCE_STYLE)
        .add(mirrored, name="mirrored", style=MIRROR_STYLE)
        .add(boundary, name="boundary", style=BOUNDARY_STYLE)
        .add(closed, name="closed", style=CLOSED_STYLE)
        .add(plane, name="plane", style=PLANE_STYLE)
        .with_camera(camera, name="profile")
        .with_light(LIGHT)
        .with_metadata(target=_format_point(centre))
    )


def print_wireframe_summary(label: str, wf: Wireframe3D) -> None:
    lower, upper = wf.bounds()
    print(
        f"{label}: {len(wf.vertices)} vertices, {len(wf.edges)} edges, "
        f"bounds={_format_point(_point_tuple(lower))} "
        f"to {_format_point(_point_tuple(upper))}"
    )


def print_mesh_summary(label: str, mesh: Mesh3D) -> None:
    lower, upper = mesh.bounds()
    print(
        f"{label}: {len(mesh.vertices)} vertices, {len(mesh.edges)} edges, "
        f"{len(mesh.faces)} faces, bounds={_format_point(_point_tuple(lower))} "
        f"to {_format_point(_point_tuple(upper))}"
    )


def _build_plane_mesh(
    lower: Point3,
    upper: Point3,
    origin: Point3,
    normal: Point3,
) -> Mesh3D:
    """Build a large flat quad at the close plane for visual reference."""
    margin = 1000  # extend beyond bounds for visibility
    if abs(normal[0]) > 0.9:  # YZ plane
        v = (
            Vec3(origin[0], lower[1] - margin, lower[2] - margin),
            Vec3(origin[0], upper[1] + margin, lower[2] - margin),
            Vec3(origin[0], upper[1] + margin, upper[2] + margin),
            Vec3(origin[0], lower[1] - margin, upper[2] + margin),
        )
    elif abs(normal[1]) > 0.9:  # XZ plane
        v = (
            Vec3(lower[0] - margin, origin[1], lower[2] - margin),
            Vec3(upper[0] + margin, origin[1], lower[2] - margin),
            Vec3(upper[0] + margin, origin[1], upper[2] + margin),
            Vec3(lower[0] - margin, origin[1], upper[2] + margin),
        )
    else:  # XY plane
        v = (
            Vec3(lower[0] - margin, lower[1] - margin, origin[2]),
            Vec3(upper[0] + margin, lower[1] - margin, origin[2]),
            Vec3(upper[0] + margin, upper[1] + margin, origin[2]),
            Vec3(lower[0] - margin, upper[1] + margin, origin[2]),
        )
    return Mesh3D(v, ((0, 1, 2), (0, 2, 3)))


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


def _combined_bounds(
    objects: tuple[Wireframe3D | Mesh3D, ...],
) -> tuple[Point3, Point3]:
    lowers: list[Point3] = []
    uppers: list[Point3] = []
    for obj in objects:
        lower, upper = obj.bounds()
        lowers.append(_point_tuple(lower))
        uppers.append(_point_tuple(upper))
    return (
        (
            min(point[0] for point in lowers),
            min(point[1] for point in lowers),
            min(point[2] for point in lowers),
        ),
        (
            max(point[0] for point in uppers),
            max(point[1] for point in uppers),
            max(point[2] for point in uppers),
        ),
    )


def _bounds_centre(lower: Point3, upper: Point3) -> Point3:
    return (
        (lower[0] + upper[0]) / 2.0,
        (lower[1] + upper[1]) / 2.0,
        (lower[2] + upper[2]) / 2.0,
    )


def _point3(value: object) -> Point3:
    x, y, z = value
    return (float(x), float(y), float(z))


def _point_tuple(value: object) -> Point3:
    point = value.tuple() if hasattr(value, "tuple") else value
    x, y, z = point
    return (float(x), float(y), float(z))


def _format_point(point: Point3) -> str:
    return f"({point[0]:g}, {point[1]:g}, {point[2]:g})"


if __name__ == "__main__":
    main()
