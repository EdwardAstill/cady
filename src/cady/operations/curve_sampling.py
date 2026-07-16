"""Numerical sampling and length helpers for cubic Bezier curves."""

from __future__ import annotations

from collections.abc import Sequence
from math import ceil, sqrt
from typing import TypeAlias

from cady.operations.primitives import cross3, length3, scale3, sub3

Point2: TypeAlias = Sequence[float]
Point3: TypeAlias = Sequence[float]


def cubic_bezier_points2(
    control_points: tuple[Point2, ...],
    *,
    tolerance: float,
) -> tuple[Point2, ...]:
    """Sample connected cubic Bezier segments in 2D."""
    points: list[Point2] = []
    samples = max(8, ceil(1.0 / sqrt(tolerance)))
    for start in range(0, len(control_points) - 1, 3):
        p0, p1, p2, p3 = control_points[start : start + 4]
        for index in range(samples + 1):
            if points and index == 0:
                continue
            t = index / samples
            u = 1.0 - t
            _append_unique_point2(
                points,
                (
                    p0[0] * (u**3)
                    + p1[0] * (3.0 * u * u * t)
                    + p2[0] * (3.0 * u * t * t)
                    + p3[0] * (t**3),
                    p0[1] * (u**3)
                    + p1[1] * (3.0 * u * u * t)
                    + p2[1] * (3.0 * u * t * t)
                    + p3[1] * (t**3),
                ),
            )
    return tuple(points)


def cubic_bezier_points3(
    control_points: tuple[Point3, ...],
    *,
    tolerance: float,
) -> tuple[Point3, ...]:
    """Adaptively sample connected cubic Bezier segments in 3D."""
    points: list[Point3] = []
    for index in range(0, len(control_points) - 1, 3):
        segment = control_points[index : index + 4]
        _append_cubic_points3(
            points,
            segment[0],
            segment[1],
            segment[2],
            segment[3],
            tolerance=tolerance,
            depth=0,
        )
    return tuple(points)


def hermite_control_points2(
    points: tuple[Point2, ...],
    vectors: tuple[Point2, ...],
    *,
    closed: bool,
) -> tuple[Point2, ...]:
    """Convert 2D Hermite points and tangents to cubic Bezier controls."""
    segment_count = len(points) if closed else len(points) - 1
    control_points: list[Point2] = []
    for index in range(segment_count):
        start = points[index]
        end = points[(index + 1) % len(points)]
        start_vector = vectors[index]
        end_vector = vectors[(index + 1) % len(points)]
        if not control_points:
            control_points.append(start)
        control_points.extend(
            (
                (start[0] + start_vector[0] / 3.0, start[1] + start_vector[1] / 3.0),
                (end[0] - end_vector[0] / 3.0, end[1] - end_vector[1] / 3.0),
                end,
            )
        )
    return tuple(control_points)


def hermite_control_points3(
    points: tuple[Point3, ...],
    vectors: tuple[Point3, ...],
) -> tuple[Point3, ...]:
    """Convert 3D Hermite points and tangents to cubic Bezier controls."""
    control_points: list[Point3] = []
    for index in range(len(points) - 1):
        start = points[index]
        end = points[index + 1]
        start_vector = vectors[index]
        end_vector = vectors[index + 1]
        if not control_points:
            control_points.append(start)
        control_points.extend(
            (
                (
                    start[0] + start_vector[0] / 3.0,
                    start[1] + start_vector[1] / 3.0,
                    start[2] + start_vector[2] / 3.0,
                ),
                (
                    end[0] - end_vector[0] / 3.0,
                    end[1] - end_vector[1] / 3.0,
                    end[2] - end_vector[2] / 3.0,
                ),
                end,
            )
        )
    return tuple(control_points)


def densify_points2(
    points: tuple[Point2, ...],
    *,
    max_segment_length: float | None,
    min_segments: int,
) -> tuple[Point2, ...]:
    """Subdivide 2D segments to satisfy length and count constraints."""
    counts = _subdivision_counts(points, max_segment_length=max_segment_length)
    while sum(counts) < min_segments:
        index = max(range(len(counts)), key=lambda item: _distance2(points[item], points[item + 1]))
        counts[index] += 1
    output: list[Point2] = []
    pairs = zip(points, points[1:], strict=False)
    for (start, end), count in zip(pairs, counts, strict=True):
        for step in range(count):
            t = step / count
            _append_unique_point2(
                output,
                (
                    start[0] + (end[0] - start[0]) * t,
                    start[1] + (end[1] - start[1]) * t,
                ),
            )
    _append_unique_point2(output, points[-1])
    return tuple(output)


def densify_points3(
    points: tuple[Point3, ...],
    *,
    max_segment_length: float | None,
    min_segments: int,
) -> tuple[Point3, ...]:
    """Subdivide 3D segments to satisfy length and count constraints."""
    counts = _subdivision_counts(points, max_segment_length=max_segment_length)
    while sum(counts) < min_segments:
        index = max(
            range(len(counts)),
            key=lambda item: length3(sub3(points[item + 1], points[item])),
        )
        counts[index] += 1
    output: list[Point3] = []
    pairs = zip(points, points[1:], strict=False)
    for (start, end), count in zip(pairs, counts, strict=True):
        for step in range(count):
            t = step / count
            _append_unique_point3(
                output,
                (
                    start[0] + (end[0] - start[0]) * t,
                    start[1] + (end[1] - start[1]) * t,
                    start[2] + (end[2] - start[2]) * t,
                ),
            )
    _append_unique_point3(output, points[-1])
    return tuple(output)


def cubic_bezier_length2(points: tuple[Point2, Point2, Point2, Point2]) -> float:
    """Return the recursively approximated length of a 2D cubic Bezier segment."""
    p0, p1, p2, p3 = points
    return _cubic_bezier_length2_recursive(p0, p1, p2, p3, depth=0)


def cubic_bezier_length3(points: tuple[Point3, Point3, Point3, Point3]) -> float:
    """Return the recursively approximated length of a 3D cubic Bezier segment."""
    p0, p1, p2, p3 = points
    return _cubic_bezier_length3_recursive(p0, p1, p2, p3, depth=0)


def _append_unique_point2(points: list[Point2], point: Point2) -> None:
    if not points or points[-1] != point:
        points.append(point)


def _append_unique_point3(points: list[Point3], point: Point3) -> None:
    if not points or points[-1] != point:
        points.append(point)


def _subdivision_counts(
    points: tuple[Point2, ...] | tuple[Point3, ...],
    *,
    max_segment_length: float | None,
) -> list[int]:
    if max_segment_length is None:
        return [1 for _start, _end in zip(points, points[1:], strict=False)]
    return [
        max(1, ceil(_point_distance(start, end) / max_segment_length))
        for start, end in zip(points, points[1:], strict=False)
    ]


def _point_distance(start: Point2 | Point3, end: Point2 | Point3) -> float:
    return sqrt(sum((right - left) ** 2 for left, right in zip(start, end, strict=True)))


def _distance2(start: Point2, end: Point2) -> float:
    return sqrt((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2)


def _cubic_bezier_length2_recursive(
    p0: Point2,
    p1: Point2,
    p2: Point2,
    p3: Point2,
    *,
    depth: int,
) -> float:
    chord = _distance2(p0, p3)
    control = _distance2(p0, p1) + _distance2(p1, p2) + _distance2(p2, p3)
    if depth >= 16 or control - chord <= 1e-9:
        return 0.5 * (control + chord)

    p01 = _midpoint2(p0, p1)
    p12 = _midpoint2(p1, p2)
    p23 = _midpoint2(p2, p3)
    p012 = _midpoint2(p01, p12)
    p123 = _midpoint2(p12, p23)
    p0123 = _midpoint2(p012, p123)
    return _cubic_bezier_length2_recursive(
        p0,
        p01,
        p012,
        p0123,
        depth=depth + 1,
    ) + _cubic_bezier_length2_recursive(
        p0123,
        p123,
        p23,
        p3,
        depth=depth + 1,
    )


def _cubic_bezier_length3_recursive(
    p0: Point3,
    p1: Point3,
    p2: Point3,
    p3: Point3,
    *,
    depth: int,
) -> float:
    chord = _point_distance(p0, p3)
    control = _point_distance(p0, p1) + _point_distance(p1, p2) + _point_distance(p2, p3)
    if depth >= 16 or control - chord <= 1e-9:
        return 0.5 * (control + chord)

    p01 = _midpoint3(p0, p1)
    p12 = _midpoint3(p1, p2)
    p23 = _midpoint3(p2, p3)
    p012 = _midpoint3(p01, p12)
    p123 = _midpoint3(p12, p23)
    p0123 = _midpoint3(p012, p123)
    return _cubic_bezier_length3_recursive(
        p0,
        p01,
        p012,
        p0123,
        depth=depth + 1,
    ) + _cubic_bezier_length3_recursive(
        p0123,
        p123,
        p23,
        p3,
        depth=depth + 1,
    )


def _midpoint2(left: Point2, right: Point2) -> Point2:
    return ((left[0] + right[0]) * 0.5, (left[1] + right[1]) * 0.5)


def _append_cubic_points3(
    points: list[Point3],
    p0: Point3,
    p1: Point3,
    p2: Point3,
    p3: Point3,
    *,
    tolerance: float,
    depth: int,
) -> None:
    if depth >= 16 or _cubic_is_flat_enough3(p0, p1, p2, p3, tolerance=tolerance):
        _append_unique_point3(points, p0)
        _append_unique_point3(points, p3)
        return

    p01 = _midpoint3(p0, p1)
    p12 = _midpoint3(p1, p2)
    p23 = _midpoint3(p2, p3)
    p012 = _midpoint3(p01, p12)
    p123 = _midpoint3(p12, p23)
    p0123 = _midpoint3(p012, p123)

    _append_cubic_points3(
        points,
        p0,
        p01,
        p012,
        p0123,
        tolerance=tolerance,
        depth=depth + 1,
    )
    _append_cubic_points3(
        points,
        p0123,
        p123,
        p23,
        p3,
        tolerance=tolerance,
        depth=depth + 1,
    )


def _midpoint3(left: Point3, right: Point3) -> Point3:
    return scale3((left[0] + right[0], left[1] + right[1], left[2] + right[2]), 0.5)


def _cubic_is_flat_enough3(
    p0: Point3,
    p1: Point3,
    p2: Point3,
    p3: Point3,
    *,
    tolerance: float,
) -> bool:
    return (
        _distance_to_chord3(p1, p0, p3) <= tolerance
        and _distance_to_chord3(p2, p0, p3) <= tolerance
    )


def _distance_to_chord3(point: Point3, start: Point3, end: Point3) -> float:
    direction = sub3(end, start)
    length = length3(direction)
    if length == 0.0:
        return length3(sub3(point, start))
    return length3(cross3(sub3(point, start), direction)) / length


__all__ = [
    "cubic_bezier_length2",
    "cubic_bezier_length3",
    "cubic_bezier_points2",
    "cubic_bezier_points3",
    "densify_points2",
    "densify_points3",
    "hermite_control_points2",
    "hermite_control_points3",
]
