"""Build a mesh from DXF intersection nodes with ball pivoting.

Usage:
    PYTHONPATH=src .venv/bin/python examples/linesplan5/ball_pivoting.py --no-view
    PYTHONPATH=src .venv/bin/python examples/linesplan5/ball_pivoting.py
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from math import floor, isfinite, sqrt
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from pc_from_dxf import (
    DEFAULT_INTERSECTION_TOLERANCE,
    DEFAULT_REPEAT_DISTANCE,
    LINESPLAN_DXF,
    dxf_intersection_pointcloud,
)

from cady import Camera, DirectionalLight, DisplayStyle, Mesh3, PointCloud3, Scene

VIEW_ASPECT = 900.0 / 700.0
FIT_PADDING = 1.08
DEFAULT_BALL_RADIUS = 900.0
DEFAULT_NEIGHBOUR_COUNT = 18
POINT_STYLE = DisplayStyle(color=(0.88, 0.45, 0.12), render_mode="points", point_size=6.0)
MESH_STYLE = DisplayStyle(color=(0.37, 0.58, 0.66), opacity=0.58, render_mode="shaded")
LIGHT = DirectionalLight(direction=(0.0, -1.0, -1.0), intensity=1.2)

Point3 = tuple[float, float, float]
EdgeIndex = tuple[int, int]
TriangleIndex = tuple[int, int, int]
PointArray = NDArray[np.float64]
IndexArray = NDArray[np.int64]
GridKey = tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class BallPivotingMesh:
    cloud: PointCloud3
    mesh: Mesh3
    curve_count: int
    raw_intersection_count: int
    intersecting_pair_count: int
    intersection_tolerance: float
    repeat_distance: float
    ball_radius: float
    neighbour_count: int
    tolerance: float


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a ball-pivoting mesh from DXF intersection nodes only.",
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
        help="Geometry tolerance used by intersection extraction and ball tests.",
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
        "--ball-radius",
        type=float,
        default=DEFAULT_BALL_RADIUS,
        help="Radius of the pivoting ball used to accept triangle candidates.",
    )
    parser.add_argument(
        "--neighbour-count",
        type=int,
        default=DEFAULT_NEIGHBOUR_COUNT,
        help="Nearest point candidates searched around each node.",
    )
    parser.add_argument(
        "--no-view",
        action="store_true",
        help="Print summaries without opening a VisPy window.",
    )
    args = parser.parse_args()

    result = ball_pivoting_mesh_from_dxf(
        args.input,
        tolerance=args.tolerance,
        intersection_tolerance=args.intersection_tolerance,
        repeat_distance=args.repeat_distance,
        ball_radius=args.ball_radius,
        neighbour_count=args.neighbour_count,
    )

    print("cady linesplan5 ball-pivoting mesh demo")
    print(f"input: {args.input}")
    print("steps: DXF wire polylines -> intersection PointCloud3 -> ball-pivoting mesh")
    print(f"polyline curves: {result.curve_count}")
    print(f"intersecting polyline pairs: {result.intersecting_pair_count}")
    print(f"raw pair intersections: {result.raw_intersection_count}")
    print(f"intersection tolerance: {result.intersection_tolerance:g}")
    print(f"repeat distance: {result.repeat_distance:g}")
    print(f"ball radius: {result.ball_radius:g}")
    print(f"neighbour count: {result.neighbour_count}")
    print(f"intersection nodes: {len(result.cloud.vertices)}")
    print_mesh_summary("ball-pivoting mesh", result.mesh)

    if args.no_view:
        print("VisPy viewer skipped.")
        return

    from cady.view import view_scene

    view_scene(
        build_scene(result),
        tolerance=args.tolerance,
        title="linesplan5 ball pivoting",
    )


def ball_pivoting_mesh_from_dxf(
    path: str | Path,
    *,
    tolerance: float = 1e-3,
    intersection_tolerance: float = DEFAULT_INTERSECTION_TOLERANCE,
    repeat_distance: float = DEFAULT_REPEAT_DISTANCE,
    ball_radius: float = DEFAULT_BALL_RADIUS,
    neighbour_count: int = DEFAULT_NEIGHBOUR_COUNT,
) -> BallPivotingMesh:
    _validate_positive(tolerance, "tolerance")
    _validate_positive(intersection_tolerance, "intersection_tolerance")
    _validate_positive(repeat_distance, "repeat_distance")

    dxf_points = dxf_intersection_pointcloud(
        path,
        tolerance=tolerance,
        intersection_tolerance=intersection_tolerance,
        repeat_distance=repeat_distance,
    )
    mesh = ball_pivoting_mesh_from_pointcloud(
        dxf_points.cloud,
        ball_radius=ball_radius,
        neighbour_count=neighbour_count,
        tolerance=tolerance,
    )
    return BallPivotingMesh(
        dxf_points.cloud,
        mesh,
        dxf_points.curve_count,
        dxf_points.raw_intersection_count,
        dxf_points.intersecting_pair_count,
        dxf_points.intersection_tolerance,
        dxf_points.repeat_distance,
        ball_radius,
        neighbour_count,
        tolerance,
    )


def ball_pivoting_mesh_from_pointcloud(
    point_cloud: PointCloud3,
    *,
    ball_radius: float = DEFAULT_BALL_RADIUS,
    neighbour_count: int = DEFAULT_NEIGHBOUR_COUNT,
    tolerance: float = 1e-3,
) -> Mesh3:
    """Build a triangle mesh from point positions only, without source curve edges."""
    _validate_positive(ball_radius, "ball_radius")
    _validate_positive(tolerance, "tolerance")
    if neighbour_count < 3:
        raise ValueError("neighbour_count must be at least 3")

    points = _points_array(point_cloud.vertices)
    if len(points) < 3:
        raise ValueError("point cloud requires at least three points")

    neighbours = _nearest_neighbour_indices(points, count=neighbour_count)
    grid = _spatial_index(points, cell_size=ball_radius)
    faces = _ball_pivot_faces(
        points,
        neighbours,
        grid,
        ball_radius=ball_radius,
        tolerance=tolerance,
    )
    if not faces:
        raise ValueError("ball pivoting found no triangle faces")

    edges = _face_edges(faces)
    return Mesh3(point_cloud.vertices, faces, edges)


def build_scene(result: BallPivotingMesh) -> Scene:
    lower, upper = result.cloud.bounds()
    camera = _fit_profile_camera(lower, upper)
    centre = _bounds_centre(lower, upper)
    return (
        Scene(name="linesplan5_ball_pivoting", camera=camera, lights=(LIGHT,))
        .add(result.mesh, name="ball_pivoting_mesh", style=MESH_STYLE)
        .add(result.cloud, name="intersection_nodes", style=POINT_STYLE)
        .with_metadata(target=_format_point(centre))
    )


def print_mesh_summary(label: str, mesh: Mesh3) -> None:
    lower, upper = mesh.bounds()
    print(
        f"{label}: {len(mesh.vertices)} vertices, {len(mesh.edges)} edges, "
        f"{len(mesh.faces)} faces, bounds={_format_point(lower)} to {_format_point(upper)}"
    )


def _ball_pivot_faces(
    points: PointArray,
    neighbours: IndexArray,
    grid: dict[GridKey, list[int]],
    *,
    ball_radius: float,
    tolerance: float,
) -> tuple[TriangleIndex, ...]:
    faces: list[TriangleIndex] = []
    seen: set[TriangleIndex] = set()
    cloud_centre = np.mean(points, axis=0)
    max_edge_sq = (2.0 * ball_radius + tolerance) ** 2

    for anchor, neighbour_row in enumerate(neighbours):
        for left, right in combinations((int(index) for index in neighbour_row), 2):
            key = tuple(sorted((anchor, left, right)))
            if len(set(key)) != 3 or key in seen:
                continue
            if _max_triangle_edge_sq(points, key) > max_edge_sq:
                continue
            centres = _ball_centres(points, key, ball_radius=ball_radius, tolerance=tolerance)
            if not centres:
                continue
            skip = set(key)
            if not any(
                _ball_is_empty(points, grid, centre, skip, ball_radius, tolerance=tolerance)
                for centre in centres
            ):
                continue

            face = _oriented_face(points, key, cloud_centre)
            seen.add(key)
            faces.append(face)
    return tuple(faces)


def _ball_centres(
    points: PointArray,
    face: TriangleIndex,
    *,
    ball_radius: float,
    tolerance: float,
) -> tuple[PointArray, ...]:
    pa, pb, pc = (points[index] for index in face)
    a = pb - pa
    b = pc - pa
    normal = np.cross(a, b)
    normal_length = float(np.linalg.norm(normal))
    if normal_length <= tolerance:
        return ()

    unit_normal = normal / normal_length
    matrix = np.stack((a, b, unit_normal), axis=0)
    rhs = np.array((float(np.dot(a, a)) / 2.0, float(np.dot(b, b)) / 2.0, 0.0))
    try:
        relative_centre = np.linalg.solve(matrix, rhs)
    except np.linalg.LinAlgError:
        return ()

    circumradius_sq = float(np.dot(relative_centre, relative_centre))
    ball_radius_sq = ball_radius * ball_radius
    if circumradius_sq > ball_radius_sq + tolerance:
        return ()

    plane_centre = pa + relative_centre
    height_sq = max(0.0, ball_radius_sq - circumradius_sq)
    height = sqrt(height_sq)
    if height <= tolerance:
        return (plane_centre,)
    return (plane_centre + unit_normal * height, plane_centre - unit_normal * height)


def _ball_is_empty(
    points: PointArray,
    grid: dict[GridKey, list[int]],
    centre: PointArray,
    skip: set[int],
    ball_radius: float,
    *,
    tolerance: float,
) -> bool:
    radius_sq = max(0.0, ball_radius - tolerance) ** 2
    for index in _nearby_point_indices(grid, centre, radius=ball_radius):
        if index in skip:
            continue
        offset = points[index] - centre
        if float(np.dot(offset, offset)) < radius_sq:
            return False
    return True


def _nearest_neighbour_indices(points: PointArray, *, count: int) -> IndexArray:
    if len(points) < 2:
        return np.empty((len(points), 0), dtype=np.int64)

    count = min(count, len(points) - 1)
    result = np.empty((len(points), count), dtype=np.int64)
    chunk_size = 256
    all_indices = np.arange(len(points))
    for start in range(0, len(points), chunk_size):
        end = min(start + chunk_size, len(points))
        block = points[start:end]
        offsets = block[:, np.newaxis, :] - points[np.newaxis, :, :]
        distances_sq = np.einsum("ijk,ijk->ij", offsets, offsets)
        distances_sq[np.arange(end - start), all_indices[start:end]] = np.inf
        nearest = np.argpartition(distances_sq, count - 1, axis=1)[:, :count]
        nearest_distances = np.take_along_axis(distances_sq, nearest, axis=1)
        order = np.argsort(nearest_distances, axis=1)
        result[start:end] = np.take_along_axis(nearest, order, axis=1)
    return result


def _spatial_index(points: PointArray, *, cell_size: float) -> dict[GridKey, list[int]]:
    grid: dict[GridKey, list[int]] = defaultdict(list)
    for index, point in enumerate(points):
        grid[_grid_key(point, cell_size=cell_size)].append(index)
    return dict(grid)


def _nearby_point_indices(
    grid: dict[GridKey, list[int]],
    centre: PointArray,
    *,
    radius: float,
) -> tuple[int, ...]:
    base = _grid_key(centre, cell_size=radius)
    result: list[int] = []
    for dx in range(-1, 2):
        for dy in range(-1, 2):
            for dz in range(-1, 2):
                result.extend(grid.get((base[0] + dx, base[1] + dy, base[2] + dz), ()))
    return tuple(result)


def _grid_key(point: PointArray, *, cell_size: float) -> GridKey:
    return (
        floor(float(point[0]) / cell_size),
        floor(float(point[1]) / cell_size),
        floor(float(point[2]) / cell_size),
    )


def _max_triangle_edge_sq(points: PointArray, face: TriangleIndex) -> float:
    a, b, c = face
    return max(
        _distance_sq(points[a], points[b]),
        _distance_sq(points[b], points[c]),
        _distance_sq(points[c], points[a]),
    )


def _distance_sq(left: PointArray, right: PointArray) -> float:
    offset = left - right
    return float(np.dot(offset, offset))


def _oriented_face(
    points: PointArray,
    face: TriangleIndex,
    cloud_centre: PointArray,
) -> TriangleIndex:
    a, b, c = face
    pa = points[a]
    normal = np.cross(points[b] - pa, points[c] - pa)
    centroid = (pa + points[b] + points[c]) / 3.0
    if float(np.dot(normal, centroid - cloud_centre)) < 0.0:
        return (a, c, b)
    return face


def _face_edges(faces: tuple[TriangleIndex, ...]) -> tuple[EdgeIndex, ...]:
    edges: set[EdgeIndex] = set()
    for face in faces:
        for start, end in zip(face, face[1:] + face[:1], strict=True):
            edges.add((min(start, end), max(start, end)))
    return tuple(sorted(edges))


def _points_array(points: tuple[Point3, ...]) -> PointArray:
    array = np.array(points, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("points must be an Nx3 array")
    return array


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
