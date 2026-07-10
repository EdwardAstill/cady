"""Cubic Bezier spline geometry in 2D and 3D."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import ceil, sqrt
from typing import TYPE_CHECKING, TypeAlias, cast

from cady.geometry._coordinates import point2, point3
from cady.operations.primitives import cross3, length3, scale3, sub3
from cady.utils import positive, positive_tolerance

Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]

if TYPE_CHECKING:
    from cady.geometry.polyline import Polyline2, Polyline3


def _append_unique_point(points: list[Point3], point: Point3) -> None:
    if not points or points[-1] != point:
        points.append(point)


def _append_unique_point2(points: list[Point2], point: Point2) -> None:
    if not points or points[-1] != point:
        points.append(point)


def _min_segments(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("min_segments must be an integer")
    if value < 1:
        raise ValueError("min_segments must be at least 1")
    return value


def _max_segment_length(value: float | None) -> float | None:
    if value is None:
        return None
    return positive(value, "max_segment_length")


@dataclass(frozen=True, slots=True, init=False)
class Spline2:
    """Cubic 2D spline made from points and tangent vectors."""

    control_points: tuple[Point2, ...]
    closed: bool = False

    def __init__(
        self,
        points: Iterable[object],
        vectors: Iterable[object] | bool | None = None,
        closed: bool = False,
    ) -> None:
        if isinstance(vectors, bool):
            closed = vectors
            vectors = None
        if vectors is None:
            control_points = tuple(point2(point) for point in points)
        else:
            control_points = _hermite_control_points2(
                tuple(point2(point) for point in points),
                tuple(point2(vector, name="vector") for vector in vectors),
                closed=bool(closed),
            )
        points = tuple(control_points)
        object.__setattr__(self, "control_points", points)
        object.__setattr__(self, "closed", bool(closed))
        if len(points) < 4 or (len(points) - 1) % 3 != 0:
            raise ValueError("Spline2 requires 3n+1 cubic Bezier control points")

    def bounds(self) -> tuple[Point2, Point2]:
        return (
            (
                min(point[0] for point in self.control_points),
                min(point[1] for point in self.control_points),
            ),
            (
                max(point[0] for point in self.control_points),
                max(point[1] for point in self.control_points),
            ),
        )

    @property
    def boundary(self) -> tuple[Point2, Point2]:
        return self.bounds()

    @property
    def length(self) -> float:
        length = sum(
            _cubic_bezier_length2(
                cast(tuple[Point2, Point2, Point2, Point2], self.control_points[index : index + 4])
            )
            for index in range(0, len(self.control_points) - 1, 3)
        )
        if self.closed and self.control_points[0] != self.control_points[-1]:
            length += _distance2(self.control_points[-1], self.control_points[0])
        return length

    def points(self) -> tuple[Point2, ...]:
        if self.closed and self.control_points[0] != self.control_points[-1]:
            return self.control_points + (self.control_points[0],)
        return self.control_points

    def discretize(
        self,
        *,
        tolerance: float,
        max_segment_length: float | None = None,
        min_segments: int = 1,
    ) -> Polyline2:
        tolerance = positive_tolerance(tolerance)
        max_segment_length = _max_segment_length(max_segment_length)
        min_segments = _min_segments(min_segments)

        points = _cubic_bezier_points2(self.control_points, tolerance=tolerance)
        if self.closed and points[0] != points[-1]:
            points = (*points, points[0])
        points = _densify_points2(
            points,
            max_segment_length=max_segment_length,
            min_segments=min_segments,
        )
        from cady.geometry.polyline import Polyline2

        return Polyline2(points, closed=self.closed)


@dataclass(frozen=True, slots=True, init=False)
class Spline3:
    """Cubic 3D spline made from points and tangent vectors."""

    control_points: tuple[Point3, ...]

    def __init__(
        self,
        points: Iterable[object],
        vectors: Iterable[object] | None = None,
    ) -> None:
        if vectors is None:
            control_points = tuple(point3(point) for point in points)
        else:
            control_points = _hermite_control_points3(
                tuple(point3(point) for point in points),
                tuple(point3(vector, name="vector") for vector in vectors),
            )
        points = tuple(control_points)
        object.__setattr__(self, "control_points", points)
        if len(points) < 4 or (len(points) - 1) % 3 != 0:
            raise ValueError("Spline3 requires 3n+1 cubic Bezier control points")

    def bounds(self) -> tuple[Point3, Point3]:
        return (
            (
                min(point[0] for point in self.control_points),
                min(point[1] for point in self.control_points),
                min(point[2] for point in self.control_points),
            ),
            (
                max(point[0] for point in self.control_points),
                max(point[1] for point in self.control_points),
                max(point[2] for point in self.control_points),
            ),
        )

    @property
    def boundary(self) -> tuple[Point3, Point3]:
        return self.bounds()

    @property
    def length(self) -> float:
        return sum(
            _cubic_bezier_length3(
                cast(tuple[Point3, Point3, Point3, Point3], self.control_points[index : index + 4])
            )
            for index in range(0, len(self.control_points) - 1, 3)
        )

    def points(self) -> tuple[Point3, ...]:
        return self.control_points

    def discretize(
        self,
        *,
        tolerance: float,
        max_segment_length: float | None = None,
        min_segments: int = 1,
    ) -> Polyline3:
        tolerance = positive_tolerance(tolerance)
        max_segment_length = _max_segment_length(max_segment_length)
        min_segments = _min_segments(min_segments)

        points: list[Point3] = []
        for index in range(0, len(self.control_points) - 1, 3):
            segment = self.control_points[index : index + 4]
            _append_cubic_points(
                points,
                segment[0],
                segment[1],
                segment[2],
                segment[3],
                tolerance=tolerance,
                depth=0,
            )
        from cady.geometry.polyline import Polyline3

        return Polyline3(
            _densify_points3(
                tuple(points),
                max_segment_length=max_segment_length,
                min_segments=min_segments,
            )
        )


def _cubic_bezier_points2(
    control_points: tuple[Point2, ...],
    *,
    tolerance: float,
) -> tuple[Point2, ...]:
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


def _hermite_control_points2(
    points: tuple[Point2, ...],
    vectors: tuple[Point2, ...],
    *,
    closed: bool,
) -> tuple[Point2, ...]:
    if closed and len(points) > 1 and points[0] == points[-1]:
        points = points[:-1]
        vectors = vectors[:-1]
    if len(points) < 2:
        raise ValueError("Spline2 requires at least two points")
    if len(vectors) != len(points):
        raise ValueError("Spline2 requires one tangent vector per point")
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


def _hermite_control_points3(
    points: tuple[Point3, ...],
    vectors: tuple[Point3, ...],
) -> tuple[Point3, ...]:
    if len(points) < 2:
        raise ValueError("Spline3 requires at least two points")
    if len(vectors) != len(points):
        raise ValueError("Spline3 requires one tangent vector per point")
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


def _densify_points2(
    points: tuple[Point2, ...],
    *,
    max_segment_length: float | None,
    min_segments: int,
) -> tuple[Point2, ...]:
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


def _densify_points3(
    points: tuple[Point3, ...],
    *,
    max_segment_length: float | None,
    min_segments: int,
) -> tuple[Point3, ...]:
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
            _append_unique_point(
                output,
                (
                    start[0] + (end[0] - start[0]) * t,
                    start[1] + (end[1] - start[1]) * t,
                    start[2] + (end[2] - start[2]) * t,
                ),
            )
    _append_unique_point(output, points[-1])
    return tuple(output)


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


def _cubic_bezier_length2(points: tuple[Point2, Point2, Point2, Point2]) -> float:
    p0, p1, p2, p3 = points
    return _cubic_bezier_length2_recursive(p0, p1, p2, p3, depth=0)


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


def _cubic_bezier_length3(points: tuple[Point3, Point3, Point3, Point3]) -> float:
    p0, p1, p2, p3 = points
    return _cubic_bezier_length3_recursive(p0, p1, p2, p3, depth=0)


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

    p01 = _midpoint(p0, p1)
    p12 = _midpoint(p1, p2)
    p23 = _midpoint(p2, p3)
    p012 = _midpoint(p01, p12)
    p123 = _midpoint(p12, p23)
    p0123 = _midpoint(p012, p123)
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


def _append_cubic_points(
    points: list[Point3],
    p0: Point3,
    p1: Point3,
    p2: Point3,
    p3: Point3,
    *,
    tolerance: float,
    depth: int,
) -> None:
    if depth >= 16 or _cubic_is_flat_enough(p0, p1, p2, p3, tolerance=tolerance):
        _append_unique_point(points, p0)
        _append_unique_point(points, p3)
        return

    p01 = _midpoint(p0, p1)
    p12 = _midpoint(p1, p2)
    p23 = _midpoint(p2, p3)
    p012 = _midpoint(p01, p12)
    p123 = _midpoint(p12, p23)
    p0123 = _midpoint(p012, p123)

    _append_cubic_points(
        points,
        p0,
        p01,
        p012,
        p0123,
        tolerance=tolerance,
        depth=depth + 1,
    )
    _append_cubic_points(
        points,
        p0123,
        p123,
        p23,
        p3,
        tolerance=tolerance,
        depth=depth + 1,
    )


def _midpoint(left: Point3, right: Point3) -> Point3:
    return (
        scale3((left[0] + right[0], left[1] + right[1], left[2] + right[2]), 0.5)
    )


def _cubic_is_flat_enough(
    p0: Point3,
    p1: Point3,
    p2: Point3,
    p3: Point3,
    *,
    tolerance: float,
) -> bool:
    return (
        _distance_to_chord(p1, p0, p3) <= tolerance
        and _distance_to_chord(p2, p0, p3) <= tolerance
    )


def _distance_to_chord(point: Point3, start: Point3, end: Point3) -> float:
    direction = sub3(end, start)
    length = length3(direction)
    if length == 0.0:
        return length3(sub3(point, start))
    return length3(cross3(sub3(point, start), direction)) / length


__all__ = ["Spline2", "Spline3"]
