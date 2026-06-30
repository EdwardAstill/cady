"""Read DXF wire polylines and turn their intersection nodes into a point cloud.

Usage:
    PYTHONPATH=src .venv/bin/python examples/linesplan4/mesh_pc_dxf.py --no-view
    PYTHONPATH=src .venv/bin/python examples/linesplan4/mesh_pc_dxf.py
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from dataclasses import dataclass
from math import cos, dist, floor, isfinite, pi, sin
from pathlib import Path

from cady import (
    Camera,
    DirectionalLight,
    DisplayStyle,
    Mesh3,
    PointCloud3,
    Polyline3,
    Scene,
    Wireframe3,
)
from cady.errors import ReadError
from cady.files import dxf
from cady.measurement.distance import closest_points_between_segments3
from cady.operations.meshes import LinesplanCurve, classify_linesplan_curves

ROOT = Path(__file__).resolve().parents[2]
LINESPLAN_DXF = ROOT / "examples" / "inputs" / "linesplan_9m.dxf"
VIEW_ASPECT = 900.0 / 700.0
FIT_PADDING = 1.08
DEFAULT_INTERSECTION_TOLERANCE = 80.0
DEFAULT_REPEAT_DISTANCE = 90.0
DIAGNOSTIC_FRONT_FRACTION = 0.075
DIAGNOSTIC_MAX_MISSES = 8
DIAGNOSTIC_RING_RADIUS = 650.0
MESH_STYLE = DisplayStyle(color=(0.48, 0.56, 0.54), opacity=0.82, render_mode="shaded")
WIRE_STYLE = DisplayStyle(color=(0.05, 0.23, 0.55), render_mode="wireframe", line_width=1.0)
POINT_STYLE = DisplayStyle(color=(0.88, 0.45, 0.12), render_mode="points", point_size=4.0)
PROJECTED_MISS_RING_STYLE = DisplayStyle(
    color=(0.55, 0.16, 0.90),
    render_mode="wireframe",
    line_width=3.0,
)
PROJECTED_MISS_LEFT_STYLE = DisplayStyle(
    color=(0.90, 0.16, 0.12),
    render_mode="wireframe",
    line_width=2.5,
)
PROJECTED_MISS_RIGHT_STYLE = DisplayStyle(
    color=(0.02, 0.58, 0.86),
    render_mode="wireframe",
    line_width=2.5,
)
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
class CurveSegment:
    source_index: int
    layer: str
    vertices: tuple[Point3, ...]
    segment: SegmentRecord


@dataclass(frozen=True, slots=True)
class IntersectionPoint:
    measure: float
    point: Point3


@dataclass(frozen=True, slots=True)
class ProjectedIntersectionMiss:
    left_source_index: int
    right_source_index: int
    left_layer: str
    right_layer: str
    left_vertices: tuple[Point3, ...]
    right_vertices: tuple[Point3, ...]
    projected_point: Point3
    left_closest: Point3
    right_closest: Point3
    gap: float


@dataclass(frozen=True, slots=True)
class PointCloudMesh:
    source: Wireframe3
    cloud: PointCloud3
    mesh: Mesh3 | None
    node_rows: tuple[tuple[Point3, ...], ...]
    guide_count: int
    rejected_count: int
    intersection_tolerance: float
    repeat_distance: float
    projected_misses: tuple[ProjectedIntersectionMiss, ...]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a point cloud from DXF linesplan polyline intersection nodes.",
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
        help="Geometry tolerance used when classifying curves.",
    )
    parser.add_argument(
        "--intersection-tolerance",
        "--snap-tolerance",
        dest="intersection_tolerance",
        type=float,
        default=DEFAULT_INTERSECTION_TOLERANCE,
        help="Maximum gap between two polylines that counts as an intersection. Defaults to 10.",
    )
    parser.add_argument(
        "--repeat-distance",
        "--min-repeat-distance",
        "--min-node-distance",
        "--exclusion-distance",
        dest="repeat_distance",
        type=float,
        default=DEFAULT_REPEAT_DISTANCE,
        help="Minimum distance before the same two polylines can intersect again. Defaults to 50.",
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

    curves = read_polyline_curves(args.input)
    source = wireframe_from_curves(curves)
    result = mesh_point_cloud_from_intersections(
        curves,
        source=source,
        tolerance=args.tolerance,
        intersection_tolerance=args.intersection_tolerance,
        repeat_distance=args.repeat_distance,
    )

    print("cady linesplan intersection point-cloud demo")
    print(f"input: {args.input}")
    print_wireframe_summary("source wireframe", result.source)
    print(
        f"classified rows: {len(result.node_rows)}, guides={result.guide_count}, "
        f"rejected={result.rejected_count}"
    )
    print(f"intersection tolerance: {result.intersection_tolerance:g}")
    print(f"repeat distance: {result.repeat_distance:g}")
    print(f"intersection nodes: {len(result.cloud.vertices)}")
    print(f"projected-only front crossings: {len(result.projected_misses)}")
    for index, miss in enumerate(result.projected_misses, start=1):
        print(
            f"  {index}: curves {miss.left_source_index}/{miss.right_source_index}, "
            f"profile={_format_point(miss.projected_point)}, gap={miss.gap:g}"
        )
    if result.mesh is None:
        print("mesh: skipped (intersection node rows are not rectangular)")
    else:
        print_mesh_summary("mesh", result.mesh)

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


def wireframe_from_curves(curves: Iterable[dxf.DxfWireCurve | LinesplanCurve]) -> Wireframe3:
    return Wireframe3.from_polylines(Polyline3(curve.vertices) for curve in curves)


def _validate_positive(value: float, name: str) -> None:
    if value <= 0.0 or not isfinite(value):
        raise ValueError(f"{name} must be positive")


def mesh_point_cloud_from_intersections(
    curves: tuple[dxf.DxfWireCurve, ...],
    *,
    source: Wireframe3,
    tolerance: float,
    intersection_tolerance: float,
    repeat_distance: float,
) -> PointCloudMesh:
    network = classify_linesplan_curves(curves, tolerance=tolerance)
    sections = tuple(sorted(network.sections, key=_station_x))
    guides = network.buttocks + network.waterlines + network.knuckles
    if len(sections) < 2:
        raise ValueError("intersection point cloud requires at least two section curves")
    if not guides:
        raise ValueError("intersection point cloud requires at least one guide curve")

    node_rows = tuple(
        row
        for row in (
            _section_intersection_nodes(
                section,
                guides,
                tolerance=tolerance,
                intersection_tolerance=intersection_tolerance,
                repeat_distance=repeat_distance,
            )
            for section in sections
        )
        if row
    )
    nodes = _unique_points(
        (point for row in node_rows for point in row),
        tolerance=intersection_tolerance,
    )
    if not nodes:
        raise ValueError("no section-guide intersection nodes were found")

    cloud = PointCloud3(nodes)
    projected_misses = _projected_intersection_misses(
        curves,
        tolerance=tolerance,
        intersection_tolerance=intersection_tolerance,
        front_fraction=DIAGNOSTIC_FRONT_FRACTION,
        max_count=DIAGNOSTIC_MAX_MISSES,
    )
    return PointCloudMesh(
        source,
        cloud,
        _mesh_from_rectangular_rows(node_rows, tolerance=tolerance),
        node_rows,
        len(guides),
        len(network.rejected),
        intersection_tolerance,
        repeat_distance,
        projected_misses,
    )


def build_scene(result: PointCloudMesh) -> Scene:
    target = result.mesh if result.mesh is not None else result.cloud
    lower, upper = target.bounds()
    camera = _fit_profile_camera(lower, upper)
    centre = _bounds_centre(lower, upper)

    scene = Scene(name="linesplan_intersection_point_cloud")
    if result.mesh is not None:
        scene = scene.add(result.mesh, name="mesh", style=MESH_STYLE)
    scene = scene.add(result.source, name="source_wireframe", style=WIRE_STYLE)
    scene = _add_projected_miss_overlays(scene, result.projected_misses)
    return (
        scene.add(result.cloud, name="intersection_nodes", style=POINT_STYLE)
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


def _section_intersection_nodes(
    section: LinesplanCurve,
    guides: tuple[LinesplanCurve, ...],
    *,
    tolerance: float,
    intersection_tolerance: float,
    repeat_distance: float,
) -> tuple[Point3, ...]:
    nodes: list[IntersectionPoint] = []
    for guide in guides:
        for node in _polyline_intersections(
            section.vertices,
            guide.vertices,
            tolerance=tolerance,
            intersection_tolerance=intersection_tolerance,
            repeat_distance=repeat_distance,
        ):
            _append_intersection_point(
                nodes,
                node,
                tolerance=intersection_tolerance,
            )
    return tuple(
        node.point
        for node in sorted(nodes, key=lambda node: node.measure)
    )


def _append_intersection_point(
    nodes: list[IntersectionPoint],
    node: IntersectionPoint,
    *,
    tolerance: float,
) -> None:
    if any(_points_close(node.point, existing.point, tolerance=tolerance) for existing in nodes):
        return
    nodes.append(node)


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


def _projected_intersection_misses(
    curves: tuple[dxf.DxfWireCurve, ...],
    *,
    tolerance: float,
    intersection_tolerance: float,
    front_fraction: float,
    max_count: int,
) -> tuple[ProjectedIntersectionMiss, ...]:
    if not curves or max_count <= 0:
        return ()
    points = tuple(point for curve in curves for point in curve.vertices)
    lower_x = min(point[0] for point in points)
    upper_x = max(point[0] for point in points)
    front_min_x = upper_x - (upper_x - lower_x) * front_fraction

    segments: list[CurveSegment] = []
    for curve in curves:
        for segment in _segment_records(curve.vertices, tolerance=tolerance):
            if segment.upper[0] >= front_min_x:
                segments.append(
                    CurveSegment(curve.source_index, curve.layer, curve.vertices, segment)
                )

    candidates: list[ProjectedIntersectionMiss] = []
    for left_index, left in enumerate(segments):
        for right in segments[left_index + 1 :]:
            if left.source_index == right.source_index:
                continue
            if not _projected_bounds_overlap(left.segment, right.segment):
                continue
            projected = _projected_segment_intersection_xz(
                left.segment.start,
                left.segment.end,
                right.segment.start,
                right.segment.end,
            )
            if projected is None:
                continue
            x, z = projected
            if x < front_min_x:
                continue
            closest = closest_points_between_segments3(
                (left.segment.start, left.segment.end),
                (right.segment.start, right.segment.end),
                tolerance=intersection_tolerance,
            )
            if closest.distance <= intersection_tolerance:
                continue
            candidates.append(
                ProjectedIntersectionMiss(
                    left.source_index,
                    right.source_index,
                    left.layer,
                    right.layer,
                    left.vertices,
                    right.vertices,
                    (x, (closest.left[1] + closest.right[1]) * 0.5, z),
                    closest.left,
                    closest.right,
                    closest.distance,
                )
            )

    return _dedupe_projected_misses(
        candidates,
        tolerance=max(intersection_tolerance, DIAGNOSTIC_RING_RADIUS * 0.25),
        max_count=max_count,
    )


def _projected_bounds_overlap(left: SegmentRecord, right: SegmentRecord) -> bool:
    return not (
        left.upper[0] < right.lower[0]
        or right.upper[0] < left.lower[0]
        or left.upper[2] < right.lower[2]
        or right.upper[2] < left.lower[2]
    )


def _projected_segment_intersection_xz(
    left_start: Point3,
    left_end: Point3,
    right_start: Point3,
    right_end: Point3,
) -> tuple[float, float] | None:
    px, py = left_start[0], left_start[2]
    rx, ry = left_end[0] - px, left_end[2] - py
    qx, qy = right_start[0], right_start[2]
    sx, sy = right_end[0] - qx, right_end[2] - qy
    denominator = _cross2(rx, ry, sx, sy)
    if abs(denominator) <= 1e-9:
        return None
    qpx, qpy = qx - px, qy - py
    left_parameter = _cross2(qpx, qpy, sx, sy) / denominator
    right_parameter = _cross2(qpx, qpy, rx, ry) / denominator
    if not (
        -1e-9 <= left_parameter <= 1.0 + 1e-9
        and -1e-9 <= right_parameter <= 1.0 + 1e-9
    ):
        return None
    return (px + left_parameter * rx, py + left_parameter * ry)


def _cross2(ax: float, ay: float, bx: float, by: float) -> float:
    return ax * by - ay * bx


def _dedupe_projected_misses(
    misses: Iterable[ProjectedIntersectionMiss],
    *,
    tolerance: float,
    max_count: int,
) -> tuple[ProjectedIntersectionMiss, ...]:
    result: list[ProjectedIntersectionMiss] = []
    for miss in sorted(misses, key=lambda item: (-item.projected_point[0], -item.gap)):
        if any(
            _profile_points_close(miss.projected_point, existing.projected_point, tolerance)
            for existing in result
        ):
            continue
        result.append(miss)
        if len(result) >= max_count:
            break
    return tuple(result)


def _profile_points_close(left: Point3, right: Point3, tolerance: float) -> bool:
    return dist((left[0], left[2]), (right[0], right[2])) <= tolerance


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


def _mesh_from_rectangular_rows(
    node_rows: tuple[tuple[Point3, ...], ...],
    *,
    tolerance: float,
) -> Mesh3 | None:
    if len(node_rows) < 2:
        return None
    row_lengths = {len(row) for row in node_rows}
    if len(row_lengths) != 1:
        return None
    columns = next(iter(row_lengths))
    if columns < 2:
        return None
    points = tuple(point for row in node_rows for point in row)
    return Mesh3.from_points(points, tolerance=tolerance)


def _add_projected_miss_overlays(
    scene: Scene,
    misses: tuple[ProjectedIntersectionMiss, ...],
) -> Scene:
    highlighted: set[int] = set()
    for index, miss in enumerate(misses, start=1):
        scene = scene.add(
            _ring_wireframe(miss.projected_point, radius=DIAGNOSTIC_RING_RADIUS),
            name=f"projected_miss_{index}_ring",
            style=PROJECTED_MISS_RING_STYLE,
        )
        for source_index, vertices, style in (
            (miss.left_source_index, miss.left_vertices, PROJECTED_MISS_LEFT_STYLE),
            (miss.right_source_index, miss.right_vertices, PROJECTED_MISS_RIGHT_STYLE),
        ):
            if source_index in highlighted:
                continue
            highlighted.add(source_index)
            scene = scene.add(
                _curve_wireframe(vertices),
                name=f"projected_miss_curve_{source_index}",
                style=style,
            )
    return scene


def _curve_wireframe(vertices: tuple[Point3, ...]) -> Wireframe3:
    return Wireframe3.from_polylines((Polyline3(vertices),))


def _ring_wireframe(centre: Point3, *, radius: float) -> Wireframe3:
    segments = 48
    points = tuple(
        (
            centre[0] + cos(2.0 * pi * index / segments) * radius,
            centre[1],
            centre[2] + sin(2.0 * pi * index / segments) * radius,
        )
        for index in range(segments)
    )
    return Wireframe3.from_polylines((Polyline3(points, closed=True),))


def _station_x(section: LinesplanCurve) -> float:
    return sum(point[0] for point in section.vertices) / len(section.vertices)


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
