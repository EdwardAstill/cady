"""Loft station polylines into a simple open Mesh3 grid."""

from __future__ import annotations

from collections.abc import Iterable
from colorsys import hsv_to_rgb
from math import dist, isfinite
from typing import TypeAlias

from wireframe import STATION_POLYLINES

from cady import (
    Camera,
    DirectionalLight,
    DisplayStyle,
    Mesh3,
    PointCloud3,
    Polyline3,
    Scene,
)

Point3: TypeAlias = tuple[float, float, float]
EdgeIndex: TypeAlias = tuple[int, int]
FaceIndex: TypeAlias = tuple[int, ...]
NodeArray: TypeAlias = tuple[tuple[Point3, ...], ...]

DEFAULT_NODES_ON_POLYLINE = 48
DEFAULT_TOLERANCE = 1e-3
DEFAULT_CONNECTION_TOLERANCE = 1000.0
VIEW_ASPECT = 900.0 / 700.0
FIT_PADDING = 1.08
LIGHT = DirectionalLight(direction=(0.0, -1.0, -1.0), intensity=1.2)
START_NODE_STYLE = DisplayStyle(color=(1.0, 0.95, 0.05), point_size=10.0)


def loft_polylines(
    polylines: Iterable[Polyline3],
    nodes_on_polyline: int,
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    connection_tolerance: float = DEFAULT_CONNECTION_TOLERANCE,
) -> Mesh3:
    """Join touching station fragments, sample rows, and connect them as a Mesh3."""
    if nodes_on_polyline < 2:
        raise ValueError("nodes_on_polyline must be at least 2")
    _validate_tolerance(tolerance)

    node_array = make_node_array(
        polylines,
        nodes_on_polyline,
        tolerance=tolerance,
        connection_tolerance=connection_tolerance,
    )
    edges, faces = edges_and_faces_from_node_array(node_array)
    vertices = tuple(point for row in node_array for point in row)
    return Mesh3(vertices, faces, edges)


def make_node_array(
    polylines: Iterable[Polyline3],
    nodes_on_polyline: int,
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    connection_tolerance: float = DEFAULT_CONNECTION_TOLERANCE,
) -> NodeArray:
    """Return one equal-width node row for each connected station polyline."""
    if nodes_on_polyline < 2:
        raise ValueError("nodes_on_polyline must be at least 2")
    _validate_tolerance(tolerance)
    _validate_tolerance(connection_tolerance)

    polylines = connect_polylines(polylines, tolerance=connection_tolerance)
    if len(polylines) < 2:
        raise ValueError("loft_polylines requires at least two polylines")

    node_array: list[tuple[Point3, ...]] = []
    for polyline in polylines:
        points = _dedupe_adjacent_points(polyline.points(), tolerance=tolerance)
        if len(points) < 2:
            raise ValueError("each polyline must contain at least two distinct points")

        segment_lengths = tuple(
            dist(start, end) for start, end in zip(points, points[1:], strict=False)
        )
        total_length = sum(segment_lengths)
        if total_length <= tolerance:
            raise ValueError("each polyline must have non-zero length")

        node_array.append(
            tuple(
                _point_at_distance(
                    points,
                    segment_lengths,
                    total_length * index / (nodes_on_polyline - 1),
                )
                for index in range(nodes_on_polyline)
            )
        )

    oriented_node_array = [node_array[0]]
    for row in node_array[1:]:
        previous = oriented_node_array[-1]
        same_direction_distance = dist(previous[0], row[0]) + dist(previous[-1], row[-1])
        flipped_direction_distance = dist(previous[0], row[-1]) + dist(previous[-1], row[0])
        if flipped_direction_distance < same_direction_distance:
            row = tuple(reversed(row))
        oriented_node_array.append(row)

    return tuple(oriented_node_array)


def connect_polylines(
    polylines: Iterable[Polyline3],
    *,
    tolerance: float = DEFAULT_CONNECTION_TOLERANCE,
) -> tuple[Polyline3, ...]:
    """Join open fragments whose endpoints meet or snap onto another fragment."""
    _validate_tolerance(tolerance)

    remaining = [_polyline_points(polyline) for polyline in polylines]
    if any(len(points) < 2 for points in remaining):
        raise ValueError("each polyline must contain at least two distinct points")

    connected: list[Polyline3] = []
    while remaining:
        points = remaining.pop(0)
        while True:
            best_index: int | None = None
            best_match: tuple[float, tuple[Point3, ...]] | None = None
            for index, candidate in enumerate(remaining):
                match = _duplicate_polyline_points(
                    points,
                    candidate,
                    tolerance=tolerance,
                )
                if match is None:
                    match = _joined_polyline_points(
                        points,
                        candidate,
                        tolerance=tolerance,
                    )
                if match is None:
                    match = _snapped_polyline_points(
                        points,
                        candidate,
                        tolerance=tolerance,
                    )
                if match is None:
                    continue
                if best_match is None or match[0] < best_match[0]:
                    best_index = index
                    best_match = match

            if best_index is None or best_match is None:
                break
            points = best_match[1]
            del remaining[best_index]

        connected.append(Polyline3(points))

    return tuple(connected)


def edges_and_faces_from_node_array(
    node_array: NodeArray,
) -> tuple[tuple[EdgeIndex, ...], tuple[FaceIndex, ...]]:
    """Build indexed grid edges and quad faces from sampled station rows."""
    if len(node_array) < 2:
        raise ValueError("node_array must contain at least two rows")

    width = len(node_array[0])
    if width < 2:
        raise ValueError("node_array rows must contain at least two nodes")
    if any(len(row) != width for row in node_array):
        raise ValueError("node_array rows must all have the same length")

    edges: set[EdgeIndex] = set()
    faces: list[FaceIndex] = []

    for row in range(len(node_array)):
        base = row * width
        for col in range(width - 1):
            edges.add((base + col, base + col + 1))

    for row in range(len(node_array) - 1):
        base = row * width
        next_base = (row + 1) * width
        for col in range(width):
            edges.add((base + col, next_base + col))
        for col in range(width - 1):
            faces.append((
                base + col,
                next_base + col,
                next_base + col + 1,
                base + col + 1,
            ))

    return tuple(sorted(edges)), tuple(faces)


def build_processed_polylines_scene(
    polylines: Iterable[Polyline3],
    *,
    connection_tolerance: float = DEFAULT_CONNECTION_TOLERANCE,
) -> Scene:
    """Build a debug scene with connected rows coloured individually."""
    processed = connect_polylines(polylines, tolerance=connection_tolerance)
    lower, upper = _polylines_bounds(processed)
    scene = Scene(
        name="processed_station_polylines",
        camera=_fit_profile_camera(lower, upper),
        lights=(LIGHT,),
    )
    for index, polyline in enumerate(processed):
        scene = scene.add(
            polyline.points(),
            name=f"station_polyline_{index:02d}",
            style=DisplayStyle(color=_polyline_color(index, len(processed))),
        )

    starts = tuple(polyline.points()[0] for polyline in processed)
    return scene.add(
        PointCloud3(starts),
        name="station_polyline_start_nodes",
        style=START_NODE_STYLE,
    )


def view_processed_polylines(polylines: Iterable[Polyline3]) -> None:
    """Open the connected station polylines with start-node markers."""
    build_processed_polylines_scene(polylines).view(title="processed station polylines")


def _duplicate_polyline_points(
    points: tuple[Point3, ...],
    candidate: tuple[Point3, ...],
    *,
    tolerance: float,
) -> tuple[float, tuple[Point3, ...]] | None:
    """Return unchanged points when the candidate is the same row."""
    if len(points) != len(candidate):
        return None

    duplicate_tolerance = min(tolerance, DEFAULT_TOLERANCE)
    same_distance = max(dist(start, end) for start, end in zip(points, candidate, strict=True))
    if same_distance <= duplicate_tolerance:
        return same_distance, points

    reversed_candidate = tuple(reversed(candidate))
    reversed_distance = max(
        dist(start, end) for start, end in zip(points, reversed_candidate, strict=True)
    )
    if reversed_distance <= duplicate_tolerance:
        return reversed_distance, points

    return None


def _joined_polyline_points(
    points: tuple[Point3, ...],
    candidate: tuple[Point3, ...],
    *,
    tolerance: float,
) -> tuple[float, tuple[Point3, ...]] | None:
    """Return a candidate join, or None for non-matches and full overlaps."""
    matches: list[tuple[float, tuple[Point3, ...]]] = []

    distance = dist(points[-1], candidate[0])
    if distance <= tolerance:
        matches.append((distance, points + candidate[1:]))

    distance = dist(points[-1], candidate[-1])
    if distance <= tolerance:
        matches.append((distance, points + tuple(reversed(candidate[:-1]))))

    distance = dist(points[0], candidate[-1])
    if distance <= tolerance:
        matches.append((distance, candidate[:-1] + points))

    distance = dist(points[0], candidate[0])
    if distance <= tolerance:
        matches.append((distance, tuple(reversed(candidate[1:])) + points))

    if len(matches) != 1:
        return None
    return matches[0]


def _snapped_polyline_points(
    points: tuple[Point3, ...],
    candidate: tuple[Point3, ...],
    *,
    tolerance: float,
) -> tuple[float, tuple[Point3, ...]] | None:
    """Return the nearest endpoint-to-segment snap candidate."""
    matches = (
        _snap_endpoint_to_polyline(candidate, points, tolerance=tolerance),
        _snap_endpoint_to_polyline(points, candidate, tolerance=tolerance),
    )
    matches = tuple(match for match in matches if match is not None)
    if not matches:
        return None
    return min(matches, key=lambda match: match[0])


def _snap_endpoint_to_polyline(
    source: tuple[Point3, ...],
    target: tuple[Point3, ...],
    *,
    tolerance: float,
) -> tuple[float, tuple[Point3, ...]] | None:
    best: tuple[float, tuple[Point3, ...]] | None = None
    for endpoint_index in (0, -1):
        endpoint = source[endpoint_index]
        source_points = source if endpoint_index == 0 else tuple(reversed(source))
        for index, (start, end) in enumerate(zip(target, target[1:], strict=False)):
            distance, snap_point, segment_position = _point_segment_distance(
                endpoint,
                start,
                end,
            )
            if not 0.0 < segment_position < 1.0 or distance > tolerance:
                continue

            snapped = (
                target[: index + 1]
                + (snap_point,)
                + source_points
                + target[index + 1 :]
            )
            if best is None or distance < best[0]:
                best = (distance, snapped)

    return best


def _point_segment_distance(
    point: Point3,
    start: Point3,
    end: Point3,
) -> tuple[float, Point3, float]:
    vector = (
        end[0] - start[0],
        end[1] - start[1],
        end[2] - start[2],
    )
    segment_length_squared = _dot(vector, vector)
    if segment_length_squared == 0.0:
        return dist(point, start), start, 0.0

    segment_position = max(
        0.0,
        min(
            1.0,
            _dot(
                (
                    point[0] - start[0],
                    point[1] - start[1],
                    point[2] - start[2],
                ),
                vector,
            )
            / segment_length_squared,
        ),
    )
    snap_point = (
        start[0] + vector[0] * segment_position,
        start[1] + vector[1] * segment_position,
        start[2] + vector[2] * segment_position,
    )
    return dist(point, snap_point), snap_point, segment_position


def _dot(left: Point3, right: Point3) -> float:
    return left[0] * right[0] + left[1] * right[1] + left[2] * right[2]


def _polyline_color(index: int, count: int) -> tuple[float, float, float]:
    hue = index / max(count, 1)
    return hsv_to_rgb(hue, 0.72, 0.92)


def _polylines_bounds(polylines: tuple[Polyline3, ...]) -> tuple[Point3, Point3]:
    points = tuple(point for polyline in polylines for point in polyline.points())
    if not points:
        raise ValueError("cannot build a scene for empty polylines")
    return (
        (
            min(point[0] for point in points),
            min(point[1] for point in points),
            min(point[2] for point in points),
        ),
        (
            max(point[0] for point in points),
            max(point[1] for point in points),
            max(point[2] for point in points),
        ),
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


def _polyline_points(polyline: Polyline3) -> tuple[Point3, ...]:
    """Return polyline points as plain float tuples."""
    return tuple((float(point[0]), float(point[1]), float(point[2])) for point in polyline.points())


def _point_at_distance(
    points: tuple[Point3, ...],
    segment_lengths: tuple[float, ...],
    target: float,
) -> Point3:
    """Interpolate the point at a target walk distance along a point chain."""
    walked = 0.0
    for start, end, length in zip(points, points[1:], segment_lengths, strict=True):
        next_walked = walked + length
        if target <= next_walked or end == points[-1]:
            if length == 0.0:
                return start
            ratio = (target - walked) / length
            return (
                start[0] + (end[0] - start[0]) * ratio,
                start[1] + (end[1] - start[1]) * ratio,
                start[2] + (end[2] - start[2]) * ratio,
            )
        walked = next_walked
    return points[-1]


def _dedupe_adjacent_points(
    points: Iterable[Point3],
    *,
    tolerance: float,
) -> tuple[Point3, ...]:
    """Drop adjacent duplicate points so zero-length segments do not affect sampling."""
    kept: list[Point3] = []
    for point in points:
        point = (float(point[0]), float(point[1]), float(point[2]))
        if kept and dist(point, kept[-1]) <= tolerance:
            continue
        kept.append(point)
    return tuple(kept)


def _validate_tolerance(tolerance: float) -> None:
    """Reject non-finite or non-positive geometric tolerances."""
    if tolerance <= 0.0 or not isfinite(tolerance):
        raise ValueError("tolerance must be positive")


def main() -> None:
    """Run the station-polyline loft example and print a mesh summary."""
    mesh = loft_polylines(STATION_POLYLINES, DEFAULT_NODES_ON_POLYLINE)
    print(
        "lofted station mesh: "
        f"{len(mesh.vertices)} vertices, {len(mesh.edges)} edges, {len(mesh.faces)} faces"
    )
    mesh.view()


def view_wireframe(polylines: Iterable[Polyline3]) -> None:
    """Open the source station polylines as a wireframe."""
    from cady import Wireframe3

    wireframe = Wireframe3.from_polylines(polylines)
    wireframe.view()


if __name__ == "__main__":
    view_processed_polylines(STATION_POLYLINES)
    main()
