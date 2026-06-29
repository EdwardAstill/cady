"""Read DXF wire polylines and turn their intersection nodes into a point cloud.

Usage:
    PYTHONPATH=src .venv/bin/python examples/linesplan4/mesh_pc_dxf.py --no-view
    PYTHONPATH=src .venv/bin/python examples/linesplan4/mesh_pc_dxf.py
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
DEFAULT_EXCLUSION_DISTANCE = 0.1
MESH_STYLE = DisplayStyle(color=(0.48, 0.56, 0.54), opacity=0.82, render_mode="shaded")
WIRE_STYLE = DisplayStyle(color=(0.05, 0.23, 0.55), render_mode="wireframe", line_width=1.0)
POINT_STYLE = DisplayStyle(color=(0.88, 0.45, 0.12), render_mode="points", point_size=4.0)
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
class IntersectionCandidate:
    gap: float
    section_measure: float
    guide_measure: float
    point: Point3


@dataclass(frozen=True, slots=True)
class PointCloudMesh:
    source: Wireframe3
    cloud: PointCloud3
    mesh: Mesh3 | None
    node_rows: tuple[tuple[Point3, ...], ...]
    guide_count: int
    rejected_count: int
    snap_tolerances: tuple[float, ...]
    exclusion_distance: float


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
        "--snap-tolerance",
        "--exclusion-distance",
        "--min-node-distance",
        dest="exclusion_distance",
        type=float,
        default=None,
        help=(
            "Minimum allowed distance between accepted nodes and the snap growth limit. "
            "Defaults to 0.1 model units."
        ),
    )
    parser.add_argument(
        "--no-view",
        action="store_true",
        help="Print summaries without opening a VisPy window.",
    )
    args = parser.parse_args()

    if args.tolerance <= 0.0 or not isfinite(args.tolerance):
        raise ValueError("tolerance must be positive")

    curves = read_polyline_curves(args.input)
    source = wireframe_from_curves(curves)
    exclusion_distance = _exclusion_distance(
        tolerance=args.tolerance,
        value=args.exclusion_distance,
    )
    snap_tolerances = _snap_tolerances(
        exclusion_distance=exclusion_distance,
    )
    result = mesh_point_cloud_from_intersections(
        curves,
        source=source,
        tolerance=args.tolerance,
        snap_tolerances=snap_tolerances,
        exclusion_distance=exclusion_distance,
    )

    print("cady linesplan intersection point-cloud demo")
    print(f"input: {args.input}")
    print_wireframe_summary("source wireframe", result.source)
    print(
        f"classified rows: {len(result.node_rows)}, guides={result.guide_count}, "
        f"rejected={result.rejected_count}"
    )
    print(f"exclusion distance: {result.exclusion_distance:g}")
    print(f"snap schedule: {_format_snap_schedule(result.snap_tolerances)}")
    print(f"intersection nodes: {len(result.cloud.vertices)}")
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


def _exclusion_distance(
    *,
    tolerance: float,
    value: float | None,
) -> float:
    if value is not None:
        if value <= 0.0 or not isfinite(value):
            raise ValueError("exclusion_distance must be positive")
        return value

    return max(tolerance, DEFAULT_EXCLUSION_DISTANCE)


def _snap_tolerances(
    *,
    exclusion_distance: float,
) -> tuple[float, ...]:
    if exclusion_distance <= 1e-12:
        return (exclusion_distance,)

    values = [1e-12]
    snap = 1e-6
    while snap < exclusion_distance * (1.0 - 1e-12):
        values.append(snap)
        snap *= 10.0
    values.append(exclusion_distance)
    return tuple(values)


def _format_snap_schedule(values: tuple[float, ...]) -> str:
    if not values:
        return ""
    labels = ["exact" if index == 0 else f"{value:g}" for index, value in enumerate(values)]
    if len(labels) <= 5:
        return " -> ".join(labels)
    return " -> ".join((*labels[:3], "...", labels[-1]))


def mesh_point_cloud_from_intersections(
    curves: tuple[dxf.DxfWireCurve, ...],
    *,
    source: Wireframe3,
    tolerance: float,
    snap_tolerances: tuple[float, ...],
    exclusion_distance: float,
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
                snap_tolerances=snap_tolerances,
                exclusion_distance=exclusion_distance,
            )
            for section in sections
        )
        if row
    )
    nodes = _unique_points(
        (point for row in node_rows for point in row),
        tolerance=exclusion_distance,
    )
    if not nodes:
        raise ValueError("no section-guide intersection nodes were found")

    cloud = PointCloud3(nodes)
    return PointCloudMesh(
        source,
        cloud,
        _mesh_from_rectangular_rows(node_rows, tolerance=tolerance),
        node_rows,
        len(guides),
        len(network.rejected),
        snap_tolerances,
        exclusion_distance,
    )


def build_scene(result: PointCloudMesh) -> Scene:
    target = result.mesh if result.mesh is not None else result.cloud
    lower, upper = target.bounds()
    camera = _fit_profile_camera(lower, upper)
    centre = _bounds_centre(lower, upper)

    scene = Scene(name="linesplan_intersection_point_cloud")
    if result.mesh is not None:
        scene = scene.add(result.mesh, name="mesh", style=MESH_STYLE)
    return (
        scene.add(result.source, name="source_wireframe", style=WIRE_STYLE)
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


def _section_intersection_nodes(
    section: LinesplanCurve,
    guides: tuple[LinesplanCurve, ...],
    *,
    tolerance: float,
    snap_tolerances: tuple[float, ...],
    exclusion_distance: float,
) -> tuple[Point3, ...]:
    candidates = _intersection_candidates(
        section,
        guides,
        tolerance=tolerance,
        snap_tolerance=snap_tolerances[-1],
    )

    accepted: list[IntersectionCandidate] = []
    for snap_tolerance in snap_tolerances:
        for candidate in candidates:
            if candidate.gap <= snap_tolerance:
                _append_candidate(
                    accepted,
                    candidate,
                    exclusion_distance=exclusion_distance,
                )
    return tuple(
        candidate.point
        for candidate in sorted(accepted, key=lambda candidate: candidate.section_measure)
    )


def _intersection_candidates(
    section: LinesplanCurve,
    guides: tuple[LinesplanCurve, ...],
    *,
    tolerance: float,
    snap_tolerance: float,
) -> tuple[IntersectionCandidate, ...]:
    candidates: list[IntersectionCandidate] = []
    for guide in guides:
        candidates.extend(
            _polyline_intersections(
                section.vertices,
                guide.vertices,
                tolerance=tolerance,
                snap_tolerance=snap_tolerance,
            )
        )
    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                candidate.gap,
                candidate.section_measure,
                candidate.guide_measure,
            ),
        )
    )


def _polyline_intersections(
    left: tuple[Point3, ...],
    right: tuple[Point3, ...],
    *,
    tolerance: float,
    snap_tolerance: float,
) -> tuple[IntersectionCandidate, ...]:
    intersections: list[IntersectionCandidate] = []
    left_segments = _segment_records(left, tolerance=tolerance)
    right_segments = _segment_records(right, tolerance=tolerance)
    for left_segment in left_segments:
        for right_segment in right_segments:
            if not _bounds_overlap(left_segment, right_segment, tolerance=snap_tolerance):
                continue
            result = closest_points_between_segments3(
                (left_segment.start, left_segment.end),
                (right_segment.start, right_segment.end),
                tolerance=snap_tolerance,
            )
            if result.distance > snap_tolerance:
                continue
            point = (
                (result.left[0] + result.right[0]) * 0.5,
                (result.left[1] + result.right[1]) * 0.5,
                (result.left[2] + result.right[2]) * 0.5,
            )
            intersections.append(
                IntersectionCandidate(
                    result.distance,
                    left_segment.offset + left_segment.length * result.left_parameter,
                    right_segment.offset + right_segment.length * result.right_parameter,
                    point,
                )
            )
    return tuple(intersections)


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


def _append_candidate(
    nodes: list[IntersectionCandidate],
    candidate: IntersectionCandidate,
    *,
    exclusion_distance: float,
) -> None:
    if any(
        _points_close(candidate.point, node.point, tolerance=exclusion_distance)
        for node in nodes
    ):
        return
    nodes.append(candidate)


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
