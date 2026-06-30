"""Read DXF wire polylines and draw their intersection nodes as a point cloud.

Usage:
    PYTHONPATH=src .venv/bin/python examples/linesplan4/pc_from_dxf.py --no-view
    PYTHONPATH=src .venv/bin/python examples/linesplan4/pc_from_dxf.py
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from dataclasses import dataclass
from math import dist, floor, isfinite
from pathlib import Path

from cady import (
    Camera,
    DirectionalLight,
    DisplayStyle,
    PointCloud3,
    Polyline3,
    Scene,
    Wireframe3,
)
from cady.errors import ReadError
from cady.files import dxf
from cady.measurement.distance import closest_points_between_segments3

ROOT = Path(__file__).resolve().parents[2]
LINESPLAN_DXF = ROOT / "examples" / "inputs" / "linesplan_9m.dxf"
VIEW_ASPECT = 900.0 / 700.0
FIT_PADDING = 1.08
DEFAULT_INTERSECTION_TOLERANCE = 80.0
DEFAULT_REPEAT_DISTANCE = 900.0
WIRE_STYLE = DisplayStyle(color=(0.05, 0.23, 0.55), render_mode="wireframe", line_width=1.0)
POINT_STYLE = DisplayStyle(color=(0.88, 0.45, 0.12), render_mode="points", point_size=7.0)
LIGHT = DirectionalLight(direction=(0.0, -1.0, -1.0), intensity=1.2)

Point3 = tuple[float, float, float]
PointKey3 = tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class SegmentRecord:
    start: Point3
    end: Point3
    offset: float
    length: float
    lower: Point3
    upper: Point3


@dataclass(frozen=True, slots=True)
class IntersectionPoint:
    measure: float
    point: Point3


@dataclass(frozen=True, slots=True)
class DxfIntersectionPointCloud:
    source: Wireframe3
    cloud: PointCloud3
    curve_count: int
    raw_intersection_count: int
    intersecting_pair_count: int
    intersection_tolerance: float
    repeat_distance: float


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build and display a point cloud from DXF wire polyline intersections.",
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
        help="Minimum segment length kept during intersection checks.",
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

    if args.tolerance <= 0.0 or not isfinite(args.tolerance):
        raise ValueError("tolerance must be positive")
    _validate_positive(args.intersection_tolerance, "intersection_tolerance")
    _validate_positive(args.repeat_distance, "repeat_distance")

    result = dxf_intersection_pointcloud(
        args.input,
        tolerance=args.tolerance,
        intersection_tolerance=args.intersection_tolerance,
        repeat_distance=args.repeat_distance,
    )

    print("cady linesplan intersection point-cloud demo")
    print(f"input: {args.input}")
    print_wireframe_summary("source wireframe", result.source)
    print(f"polyline curves: {result.curve_count}")
    print(f"intersecting polyline pairs: {result.intersecting_pair_count}")
    print(f"raw pair intersections: {result.raw_intersection_count}")
    print(f"intersection tolerance: {result.intersection_tolerance:g}")
    print(f"repeat distance: {result.repeat_distance:g}")
    print(f"intersection nodes: {len(result.cloud.vertices)}")

    if args.no_view:
        print("VisPy viewer skipped.")
        return

    from cady.view import view_scene

    view_scene(build_scene(result), tolerance=args.tolerance, title="linesplan intersection nodes")


def read_polyline_curves(path: Path) -> tuple[dxf.DxfWireCurve, ...]:
    curves = tuple(curve for curve in dxf.read_curves(path) if len(curve.vertices) >= 2)
    if len(curves) < 2:
        raise ReadError("DXF contained fewer than two supported wire polylines")
    return curves


def wireframe_from_curves(curves: Iterable[dxf.DxfWireCurve]) -> Wireframe3:
    return Wireframe3.from_polylines(Polyline3(curve.vertices) for curve in curves)


def pointcloud_from_dxf(
    path: str | Path,
    *,
    tolerance: float = 1e-3,
    intersection_tolerance: float = DEFAULT_INTERSECTION_TOLERANCE,
    repeat_distance: float = DEFAULT_REPEAT_DISTANCE,
) -> PointCloud3:
    """Return intersection nodes from a DXF wire drawing as an unconnected point cloud."""
    return dxf_intersection_pointcloud(
        path,
        tolerance=tolerance,
        intersection_tolerance=intersection_tolerance,
        repeat_distance=repeat_distance,
    ).cloud


def point_cloud_from_dxf(
    path: str | Path,
    *,
    tolerance: float = 1e-3,
    intersection_tolerance: float = DEFAULT_INTERSECTION_TOLERANCE,
    repeat_distance: float = DEFAULT_REPEAT_DISTANCE,
) -> PointCloud3:
    """Alias for callers who prefer the separated point_cloud spelling."""
    return pointcloud_from_dxf(
        path,
        tolerance=tolerance,
        intersection_tolerance=intersection_tolerance,
        repeat_distance=repeat_distance,
    )


def dxf_intersection_pointcloud(
    path: str | Path,
    *,
    tolerance: float = 1e-3,
    intersection_tolerance: float = DEFAULT_INTERSECTION_TOLERANCE,
    repeat_distance: float = DEFAULT_REPEAT_DISTANCE,
) -> DxfIntersectionPointCloud:
    _validate_positive(tolerance, "tolerance")
    _validate_positive(intersection_tolerance, "intersection_tolerance")
    _validate_positive(repeat_distance, "repeat_distance")
    curves = read_polyline_curves(Path(path))
    return pointcloud_from_intersections(
        curves,
        source=wireframe_from_curves(curves),
        tolerance=tolerance,
        intersection_tolerance=intersection_tolerance,
        repeat_distance=repeat_distance,
    )


def _validate_positive(value: float, name: str) -> None:
    if value <= 0.0 or not isfinite(value):
        raise ValueError(f"{name} must be positive")


def pointcloud_from_intersections(
    curves: tuple[dxf.DxfWireCurve, ...],
    *,
    source: Wireframe3,
    tolerance: float,
    intersection_tolerance: float,
    repeat_distance: float,
) -> DxfIntersectionPointCloud:
    intersections, intersecting_pair_count = _all_polyline_intersections(
        curves,
        tolerance=tolerance,
        intersection_tolerance=intersection_tolerance,
        repeat_distance=repeat_distance,
    )
    nodes = _unique_points(
        (intersection.point for intersection in intersections),
        tolerance=intersection_tolerance,
    )
    if not nodes:
        raise ValueError("no polyline intersection nodes were found")

    return DxfIntersectionPointCloud(
        source,
        PointCloud3(nodes),
        len(curves),
        len(intersections),
        intersecting_pair_count,
        intersection_tolerance,
        repeat_distance,
    )


def build_scene(result: DxfIntersectionPointCloud) -> Scene:
    lower, upper = result.source.bounds()
    camera = _fit_profile_camera(lower, upper)
    centre = _bounds_centre(lower, upper)

    return (
        Scene(name="linesplan_intersection_point_cloud", camera=camera, lights=(LIGHT,))
        .add(result.source, name="source_wireframe", style=WIRE_STYLE)
        .add(result.cloud, name="intersection_nodes", style=POINT_STYLE)
        .with_metadata(target=_format_point(centre))
    )


def print_wireframe_summary(label: str, wireframe: Wireframe3) -> None:
    lower, upper = wireframe.bounds()
    print(
        f"{label}: {len(wireframe.vertices)} vertices, {len(wireframe.edges)} edges, "
        f"bounds={_format_point(lower)} to {_format_point(upper)}"
    )


def _all_polyline_intersections(
    curves: tuple[dxf.DxfWireCurve, ...],
    *,
    tolerance: float,
    intersection_tolerance: float,
    repeat_distance: float,
) -> tuple[tuple[IntersectionPoint, ...], int]:
    nodes: list[IntersectionPoint] = []
    intersecting_pair_count = 0
    for left_index, left in enumerate(curves):
        for right in curves[left_index + 1 :]:
            pair_nodes = _polyline_intersections(
                left.vertices,
                right.vertices,
                tolerance=tolerance,
                intersection_tolerance=intersection_tolerance,
                repeat_distance=repeat_distance,
            )
            if not pair_nodes:
                continue
            intersecting_pair_count += 1
            nodes.extend(pair_nodes)
    return tuple(nodes), intersecting_pair_count


def _append_pair_intersection(
    nodes: list[IntersectionPoint],
    node: IntersectionPoint,
    *,
    repeat_distance: float,
) -> None:
    if any(
        _points_close(node.point, existing.point, tolerance=repeat_distance)
        for existing in nodes
    ):
        return
    nodes.append(node)


def _intersection_point(
    left_segment: SegmentRecord,
    right_segment: SegmentRecord,
    *,
    intersection_tolerance: float,
) -> tuple[float, float, Point3] | None:
    result = closest_points_between_segments3(
        (left_segment.start, left_segment.end),
        (right_segment.start, right_segment.end),
        tolerance=intersection_tolerance,
    )
    if result.distance > intersection_tolerance:
        return None

    point = (
        (result.left[0] + result.right[0]) * 0.5,
        (result.left[1] + result.right[1]) * 0.5,
        (result.left[2] + result.right[2]) * 0.5,
    )
    measure = left_segment.offset + left_segment.length * result.left_parameter
    return measure, result.distance, point


def _polyline_intersections(
    left: tuple[Point3, ...],
    right: tuple[Point3, ...],
    *,
    tolerance: float,
    intersection_tolerance: float,
    repeat_distance: float,
) -> tuple[IntersectionPoint, ...]:
    candidates: list[tuple[float, float, Point3]] = []
    left_segments = _segment_records(left, tolerance=tolerance)
    right_segments = _segment_records(right, tolerance=tolerance)
    for left_segment in left_segments:
        for right_segment in right_segments:
            if not _bounds_overlap(
                left_segment,
                right_segment,
                tolerance=intersection_tolerance,
            ):
                continue
            intersection = _intersection_point(
                left_segment,
                right_segment,
                intersection_tolerance=intersection_tolerance,
            )
            if intersection is not None:
                candidates.append(intersection)

    nodes: list[IntersectionPoint] = []
    for measure, _gap, point in sorted(candidates, key=lambda item: (item[0], item[1])):
        _append_pair_intersection(
            nodes,
            IntersectionPoint(measure, point),
            repeat_distance=repeat_distance,
        )
    return tuple(nodes)


def _segment_records(
    vertices: tuple[Point3, ...],
    *,
    tolerance: float,
) -> tuple[SegmentRecord, ...]:
    records: list[SegmentRecord] = []
    offset = 0.0
    for start, end in zip(vertices, vertices[1:], strict=False):
        length = dist(start, end)
        if length > tolerance:
            records.append(
                SegmentRecord(
                    start,
                    end,
                    offset,
                    length,
                    (
                        min(start[0], end[0]),
                        min(start[1], end[1]),
                        min(start[2], end[2]),
                    ),
                    (
                        max(start[0], end[0]),
                        max(start[1], end[1]),
                        max(start[2], end[2]),
                    ),
                )
            )
        offset += length
    return tuple(records)


def _bounds_overlap(
    left: SegmentRecord,
    right: SegmentRecord,
    *,
    tolerance: float,
) -> bool:
    return not (
        left.upper[0] + tolerance < right.lower[0]
        or right.upper[0] + tolerance < left.lower[0]
        or left.upper[1] + tolerance < right.lower[1]
        or right.upper[1] + tolerance < left.lower[1]
        or left.upper[2] + tolerance < right.lower[2]
        or right.upper[2] + tolerance < left.lower[2]
    )


def _unique_points(points: Iterable[Point3], *, tolerance: float) -> tuple[Point3, ...]:
    unique: list[Point3] = []
    buckets: dict[PointKey3, list[Point3]] = {}
    for point in points:
        if any(
            _points_close(point, existing, tolerance=tolerance)
            for key in _neighbour_keys(_point_key(point, tolerance=tolerance))
            for existing in buckets.get(key, ())
        ):
            continue
        unique.append(point)
        buckets.setdefault(_point_key(point, tolerance=tolerance), []).append(point)
    return tuple(unique)


def _point_key(point: Point3, *, tolerance: float) -> PointKey3:
    return (
        floor(point[0] / tolerance),
        floor(point[1] / tolerance),
        floor(point[2] / tolerance),
    )


def _neighbour_keys(key: PointKey3) -> Iterable[PointKey3]:
    x, y, z = key
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                yield (x + dx, y + dy, z + dz)


def _points_close(left: Point3, right: Point3, *, tolerance: float) -> bool:
    return dist(left, right) <= tolerance


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
