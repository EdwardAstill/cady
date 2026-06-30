"""Build a mesh from the DXF intersection point cloud.

Usage:
    PYTHONPATH=src .venv/bin/python examples/linesplan4/mesh_from_pc.py --no-view
    PYTHONPATH=src .venv/bin/python examples/linesplan4/mesh_from_pc.py
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from math import isfinite
from pathlib import Path

from pc_from_dxf import (
    DEFAULT_INTERSECTION_TOLERANCE,
    DEFAULT_REPEAT_DISTANCE,
    LINESPLAN_DXF,
    dxf_intersection_pointcloud,
)

from cady import (
    Camera,
    DirectionalLight,
    DisplayStyle,
    Mesh3,
    PointCloud3,
    Scene,
    Wireframe3,
)

VIEW_ASPECT = 900.0 / 700.0
FIT_PADDING = 1.08
WIRE_STYLE = DisplayStyle(color=(0.05, 0.23, 0.55), render_mode="wireframe", line_width=1.0)
POINT_STYLE = DisplayStyle(color=(0.88, 0.45, 0.12), render_mode="points", point_size=6.0)
MESH_STYLE = DisplayStyle(color=(0.42, 0.61, 0.34), opacity=0.58, render_mode="shaded")
LIGHT = DirectionalLight(direction=(0.0, -1.0, -1.0), intensity=1.2)

Point3 = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class DxfPointCloudMesh:
    source: Wireframe3
    cloud: PointCloud3
    mesh: Mesh3
    curve_count: int
    raw_intersection_count: int
    intersecting_pair_count: int
    intersection_tolerance: float
    repeat_distance: float
    mesh_tolerance: float


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build and display a Mesh3 reconstructed from DXF intersection points.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=LINESPLAN_DXF,
        help="DXF file to read.",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=1e-3,
        help="Tolerance passed to DXF sampling and Mesh3.from_points.",
    )
    parser.add_argument(
        "--intersection-tolerance",
        "--snap-tolerance",
        dest="intersection_tolerance",
        type=float,
        default=DEFAULT_INTERSECTION_TOLERANCE,
        help="Maximum gap between two polylines that counts as an intersection.",
    )
    parser.add_argument(
        "--repeat-distance",
        "--min-repeat-distance",
        "--min-node-distance",
        "--exclusion-distance",
        dest="repeat_distance",
        type=float,
        default=DEFAULT_REPEAT_DISTANCE,
        help="Minimum distance before the same two polylines can intersect again.",
    )
    parser.add_argument(
        "--no-view",
        action="store_true",
        help="Print summaries without opening a VisPy window.",
    )
    args = parser.parse_args()

    _validate_positive(args.tolerance, "tolerance")
    _validate_positive(args.intersection_tolerance, "intersection_tolerance")
    _validate_positive(args.repeat_distance, "repeat_distance")

    result = mesh_from_dxf_pointcloud(
        args.input,
        tolerance=args.tolerance,
        intersection_tolerance=args.intersection_tolerance,
        repeat_distance=args.repeat_distance,
    )

    print("cady linesplan DXF point-cloud meshing demo")
    print(f"input: {args.input}")
    print("steps: DXF wire polylines -> intersection PointCloud3 -> Mesh3.from_points")
    print_wireframe_summary("source wireframe", result.source)
    print(f"polyline curves: {result.curve_count}")
    print(f"intersecting polyline pairs: {result.intersecting_pair_count}")
    print(f"raw pair intersections: {result.raw_intersection_count}")
    print(f"intersection tolerance: {result.intersection_tolerance:g}")
    print(f"repeat distance: {result.repeat_distance:g}")
    print(f"point-cloud nodes: {len(result.cloud.vertices)}")
    print_mesh_summary("mesh from point cloud", result.mesh)
    print(f"mesh tolerance: {result.mesh_tolerance:g}")

    if args.no_view:
        print("VisPy viewer skipped.")
        return

    from cady.view import view_scene

    view_scene(
        build_scene(result),
        tolerance=args.tolerance,
        title="linesplan mesh from point cloud",
    )


def mesh_from_pointcloud(point_cloud: PointCloud3, *, tolerance: float = 1e-3) -> Mesh3:
    """Reconstruct a triangle mesh from a PointCloud3."""
    _validate_positive(tolerance, "tolerance")
    return Mesh3.from_points(point_cloud, tolerance=tolerance)


def mesh_from_dxf_pointcloud(
    path: str | Path,
    *,
    tolerance: float = 1e-3,
    intersection_tolerance: float = DEFAULT_INTERSECTION_TOLERANCE,
    repeat_distance: float = DEFAULT_REPEAT_DISTANCE,
) -> DxfPointCloudMesh:
    _validate_positive(tolerance, "tolerance")
    dxf_points = dxf_intersection_pointcloud(
        path,
        tolerance=tolerance,
        intersection_tolerance=intersection_tolerance,
        repeat_distance=repeat_distance,
    )
    mesh = mesh_from_pointcloud(dxf_points.cloud, tolerance=tolerance)
    return DxfPointCloudMesh(
        dxf_points.source,
        dxf_points.cloud,
        mesh,
        dxf_points.curve_count,
        dxf_points.raw_intersection_count,
        dxf_points.intersecting_pair_count,
        dxf_points.intersection_tolerance,
        dxf_points.repeat_distance,
        tolerance,
    )


def build_scene(result: DxfPointCloudMesh) -> Scene:
    lower, upper = result.source.bounds()
    camera = _fit_profile_camera(lower, upper)
    centre = _bounds_centre(lower, upper)

    return (
        Scene(name="linesplan_mesh_from_point_cloud")
        .add(result.source, name="source_wireframe", style=WIRE_STYLE)
        .add(result.mesh, name="mesh_from_point_cloud", style=MESH_STYLE)
        .add(result.cloud, name="intersection_nodes", style=POINT_STYLE)
        .with_camera(camera, name="profile")
        .with_light(LIGHT)
        .with_metadata(target=_format_point(centre))
    )


def print_wireframe_summary(label: str, wireframe: Wireframe3) -> None:
    lower, upper = wireframe.bounds()
    print(
        f"{label}: {len(wireframe.vertices)} vertices, {len(wireframe.edges)} edges, "
        f"bounds={_format_point(lower)} to {_format_point(upper)}"
    )


def print_mesh_summary(label: str, mesh: Mesh3) -> None:
    lower, upper = mesh.bounds()
    print(
        f"{label}: {len(mesh.vertices)} vertices, {len(mesh.edges)} edges, "
        f"{len(mesh.faces)} faces, bounds={_format_point(lower)} to {_format_point(upper)}"
    )


def _validate_positive(value: float, name: str) -> None:
    if value <= 0.0 or not isfinite(value):
        raise ValueError(f"{name} must be positive")


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


def _format_point(point: Point3) -> str:
    return f"({point[0]:g}, {point[1]:g}, {point[2]:g})"


if __name__ == "__main__":
    main()
