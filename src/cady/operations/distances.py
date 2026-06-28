"""Distance and closest-point algorithms for numeric geometry values."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite, sqrt
from numbers import Real
from typing import TypeAlias, TypeGuard

from cady.operations.coordinates import distance2 as _distance2
from cady.operations.coordinates import distance3 as _distance3
from cady.operations.coordinates import dot3, scale3, sub3
from cady.utils import positive_tolerance

Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]
Line2Points: TypeAlias = tuple[Point2, Point2]
Line3Points: TypeAlias = tuple[Point3, Point3]


@dataclass(frozen=True, slots=True)
class ClosestPoints2:
    """Closest points between two bounded 2D line segments."""

    distance: float
    left: Point2
    right: Point2
    left_parameter: float
    right_parameter: float


@dataclass(frozen=True, slots=True)
class ClosestPoints3:
    """Closest points between two bounded 3D line segments."""

    distance: float
    left: Point3
    right: Point3
    left_parameter: float
    right_parameter: float


@dataclass(frozen=True, slots=True)
class LinePlaneClosestPoint:
    """Minimum-distance result between a bounded 3D segment and a plane."""

    distance: float
    point: Point3
    line_parameter: float


def distance(left: object, right: object, *, tolerance: float = 1e-9) -> float:
    """Return the minimum distance between supported geometry values.

    Supported pairs are point/point, point/plane, line/line, and line/plane.
    Line inputs are treated as bounded segments, matching ``Line2`` and
    ``Line3``.
    """
    tolerance = positive_tolerance(tolerance)

    left_point = point_tuple(left)
    right_point = point_tuple(right)
    if left_point is not None and right_point is not None:
        if len(left_point) != len(right_point):
            raise TypeError("point dimensions must match")
        if len(left_point) == 2:
            return _distance2(_as_point2(left_point), _as_point2(right_point))
        return _distance3(
            _as_point3(left_point, "left point"),
            _as_point3(right_point, "right point"),
        )

    left_plane = plane_origin_normal(left)
    right_plane = plane_origin_normal(right)
    if left_point is not None and right_plane is not None:
        return abs(signed_distance_to_plane(_as_point3(left_point, "left point"), *right_plane))
    if right_point is not None and left_plane is not None:
        return abs(signed_distance_to_plane(_as_point3(right_point, "right point"), *left_plane))

    left_line = line_points(left)
    right_line = line_points(right)
    if left_line is not None and right_line is not None:
        if len(left_line[0]) != len(right_line[0]):
            raise TypeError("line dimensions must match")
        if len(left_line[0]) == 2:
            return closest_points_between_segments2(
                _as_line2(left_line),
                _as_line2(right_line),
                tolerance=tolerance,
            ).distance
        return closest_points_between_segments3(
            _as_line3(left_line, "left line"),
            _as_line3(right_line, "right line"),
            tolerance=tolerance,
        ).distance

    if left_line is not None and right_plane is not None:
        return closest_line_plane(_as_line3(left_line, "left line"), *right_plane).distance
    if right_line is not None and left_plane is not None:
        return closest_line_plane(_as_line3(right_line, "right line"), *left_plane).distance

    raise TypeError(f"unsupported distance operands: {type(left).__name__}, {type(right).__name__}")


def signed_distance_to_plane(point: Point3, origin: Point3, normal: Point3) -> float:
    """Return the signed perpendicular distance from ``point`` to a plane."""
    unit = _normalised3(normal, "normal")
    return dot3(sub3(point, origin), unit)


def closest_line_plane(line: Line3Points, origin: Point3, normal: Point3) -> LinePlaneClosestPoint:
    """Return the closest point on a bounded segment to a plane."""
    unit = _normalised3(normal, "normal")
    start, end = line
    start_distance = dot3(sub3(start, origin), unit)
    end_distance = dot3(sub3(end, origin), unit)
    if start_distance == 0.0:
        return LinePlaneClosestPoint(0.0, start, 0.0)
    if end_distance == 0.0:
        return LinePlaneClosestPoint(0.0, end, 1.0)
    if (start_distance < 0.0 < end_distance) or (end_distance < 0.0 < start_distance):
        parameter = start_distance / (start_distance - end_distance)
        return LinePlaneClosestPoint(0.0, _lerp3(start, end, parameter), parameter)
    if abs(start_distance) <= abs(end_distance):
        return LinePlaneClosestPoint(abs(start_distance), start, 0.0)
    return LinePlaneClosestPoint(abs(end_distance), end, 1.0)


def closest_points_between_segments2(
    left: Line2Points,
    right: Line2Points,
    *,
    tolerance: float = 1e-9,
) -> ClosestPoints2:
    """Return closest points between two bounded 2D segments."""
    result = closest_points_between_segments3(
        (_point2_to_3(left[0]), _point2_to_3(left[1])),
        (_point2_to_3(right[0]), _point2_to_3(right[1])),
        tolerance=tolerance,
    )
    return ClosestPoints2(
        result.distance,
        (result.left[0], result.left[1]),
        (result.right[0], result.right[1]),
        result.left_parameter,
        result.right_parameter,
    )


def closest_points_between_segments3(
    left: Line3Points,
    right: Line3Points,
    *,
    tolerance: float = 1e-9,
) -> ClosestPoints3:
    """Return closest points between two bounded 3D segments."""
    tolerance = positive_tolerance(tolerance)
    p1, q1 = left
    p2, q2 = right
    d1 = sub3(q1, p1)
    d2 = sub3(q2, p2)
    r = sub3(p1, p2)
    a = dot3(d1, d1)
    e = dot3(d2, d2)
    f = dot3(d2, r)

    if a <= tolerance * tolerance and e <= tolerance * tolerance:
        return ClosestPoints3(_distance3(p1, p2), p1, p2, 0.0, 0.0)
    if a <= tolerance * tolerance:
        s = 0.0
        t = _clamp(f / e)
    else:
        c = dot3(d1, r)
        if e <= tolerance * tolerance:
            t = 0.0
            s = _clamp(-c / a)
        else:
            b = dot3(d1, d2)
            denominator = a * e - b * b
            s = _clamp((b * f - c * e) / denominator) if denominator != 0.0 else 0.0
            t = (b * s + f) / e
            if t < 0.0:
                t = 0.0
                s = _clamp(-c / a)
            elif t > 1.0:
                t = 1.0
                s = _clamp((b - c) / a)

    left_point = _lerp3(p1, q1, s)
    right_point = _lerp3(p2, q2, t)
    return ClosestPoints3(_distance3(left_point, right_point), left_point, right_point, s, t)


def line_points(value: object) -> tuple[tuple[float, ...], tuple[float, ...]] | None:
    start = getattr(value, "start", None)
    end = getattr(value, "end", None)
    if start is not None and end is not None:
        start_point = point_tuple(start)
        end_point = point_tuple(end)
        if start_point is None or end_point is None or len(start_point) != len(end_point):
            raise ValueError("line endpoints must be finite points with matching dimensions")
        return start_point, end_point
    if is_sequence(value) and len(value) == 2:
        first = point_tuple(value[0])
        second = point_tuple(value[1])
        if first is not None and second is not None and len(first) == len(second):
            return first, second
    return None


def plane_origin_normal(value: object) -> tuple[Point3, Point3] | None:
    origin = getattr(value, "origin", None)
    normal = getattr(value, "normal", None)
    if origin is None or normal is None:
        return None
    origin_point = point_tuple(origin)
    normal_point = point_tuple(normal)
    if origin_point is None or normal_point is None:
        raise ValueError("plane origin and normal must be finite 3D points")
    if len(origin_point) != 3 or len(normal_point) != 3:
        raise ValueError("plane origin and normal must be 3D")
    return origin_point, normal_point


def point_tuple(value: object) -> tuple[float, ...] | None:
    if not is_sequence(value) or len(value) not in {2, 3}:
        return None
    values: list[float] = []
    for item in value:
        if not isinstance(item, Real):
            return None
        number = float(item)
        if not isfinite(number):
            raise ValueError("points must contain finite values")
        values.append(number)
    return tuple(values)


def _as_point2(value: tuple[float, ...]) -> Point2:
    if len(value) != 2:
        raise TypeError("point must be 2D")
    return (value[0], value[1])


def _as_point3(value: tuple[float, ...], name: str) -> Point3:
    if len(value) != 3:
        raise TypeError(f"{name} must be 3D")
    return (value[0], value[1], value[2])


def _as_line2(value: tuple[tuple[float, ...], tuple[float, ...]]) -> Line2Points:
    return (_as_point2(value[0]), _as_point2(value[1]))


def _as_line3(value: tuple[tuple[float, ...], tuple[float, ...]], name: str) -> Line3Points:
    return (_as_point3(value[0], f"{name} start"), _as_point3(value[1], f"{name} end"))


def _normalised3(vector: Point3, name: str) -> Point3:
    length = sqrt(dot3(vector, vector))
    if length == 0.0:
        raise ValueError(f"{name} must be non-zero")
    return scale3(vector, 1.0 / length)


def _lerp3(start: Point3, end: Point3, parameter: float) -> Point3:
    return (
        start[0] + (end[0] - start[0]) * parameter,
        start[1] + (end[1] - start[1]) * parameter,
        start[2] + (end[2] - start[2]) * parameter,
    )


def _point2_to_3(point: Point2) -> Point3:
    return (point[0], point[1], 0.0)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def is_sequence(value: object) -> TypeGuard[Sequence[object]]:
    return isinstance(value, Sequence) and not isinstance(value, str | bytes)


__all__ = [
    "ClosestPoints2",
    "ClosestPoints3",
    "LinePlaneClosestPoint",
    "closest_line_plane",
    "closest_points_between_segments2",
    "closest_points_between_segments3",
    "distance",
    "line_points",
    "plane_origin_normal",
    "point_tuple",
    "signed_distance_to_plane",
]
