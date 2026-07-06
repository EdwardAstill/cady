"""Intersection measurements for geometry values."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import TypeAlias

from cady.measurement.distance import (
    closest_points_between_segments3,
    line_points,
    plane_origin_normal,
)
from cady.operations.primitives import cross3, dot3, scale3, sub3
from cady.utils import positive_tolerance

Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]
Line2Points: TypeAlias = tuple[Point2, Point2]
Line3Points: TypeAlias = tuple[Point3, Point3]


@dataclass(frozen=True, slots=True)
class LineIntersection2:
    """Unique intersection point between two bounded 2D segments."""

    point: Point2
    left_parameter: float
    right_parameter: float


@dataclass(frozen=True, slots=True)
class LineIntersection3:
    """Unique intersection point between two bounded 3D segments."""

    point: Point3
    left_parameter: float
    right_parameter: float


@dataclass(frozen=True, slots=True)
class LinePlaneIntersection:
    """Intersection point between a 3D line segment and a plane."""

    point: Point3
    line_parameter: float


@dataclass(frozen=True, slots=True)
class InfiniteLine3:
    """Infinite 3D line represented by point and direction."""

    point: Point3
    direction: Point3


def intersection(
    left: object,
    right: object,
    *,
    tolerance: float = 1e-9,
) -> object | None:
    """Return the intersection result for supported geometry pairs.

    Supported pairs are line/line, line/plane, plane/plane, and planar
    ``Surface3``/``Surface3``. Bounded line inputs only intersect when their
    segment ranges overlap at a unique point.
    """
    tolerance = positive_tolerance(tolerance)
    left_surface_plane = _surface_plane(left)
    right_surface_plane = _surface_plane(right)
    if left_surface_plane is not None and right_surface_plane is not None:
        return _plane_plane_intersection(
            left_surface_plane[0],
            left_surface_plane[1],
            right_surface_plane[0],
            right_surface_plane[1],
            tolerance=tolerance,
        )

    left_plane = plane_origin_normal(left)
    right_plane = plane_origin_normal(right)
    if left_plane is not None and right_plane is not None:
        return _plane_plane_intersection(
            left_plane[0],
            left_plane[1],
            right_plane[0],
            right_plane[1],
            tolerance=tolerance,
        )

    left_line = line_points(left)
    right_line = line_points(right)
    if left_line is not None and right_line is not None:
        if len(left_line[0]) != len(right_line[0]):
            raise TypeError("line dimensions must match")
        if len(left_line[0]) == 2:
            return _line2_line2_intersection(
                _as_line2(left_line),
                _as_line2(right_line),
                tolerance=tolerance,
            )
        return _line3_line3_intersection(
            _as_line3(left_line, "left line"),
            _as_line3(right_line, "right line"),
            tolerance=tolerance,
        )

    if left_line is not None and right_plane is not None:
        return _line3_plane_intersection(
            _as_line3(left_line, "left line"),
            *right_plane,
            tolerance=tolerance,
        )
    if right_line is not None and left_plane is not None:
        return _line3_plane_intersection(
            _as_line3(right_line, "right line"),
            *left_plane,
            tolerance=tolerance,
        )

    raise TypeError(
        f"unsupported intersection operands: {type(left).__name__}, {type(right).__name__}"
    )


def _line2_line2_intersection(
    left: Line2Points,
    right: Line2Points,
    *,
    tolerance: float = 1e-9,
) -> LineIntersection2 | None:
    """Return the unique intersection between two bounded 2D segments."""
    tolerance = positive_tolerance(tolerance)
    p, p_end = left
    q, q_end = right
    r = (p_end[0] - p[0], p_end[1] - p[1])
    s = (q_end[0] - q[0], q_end[1] - q[1])
    denominator = _cross2(r, s)
    if abs(denominator) <= tolerance:
        return None
    qp = (q[0] - p[0], q[1] - p[1])
    t = _cross2(qp, s) / denominator
    u = _cross2(qp, r) / denominator
    if not (-tolerance <= t <= 1.0 + tolerance and -tolerance <= u <= 1.0 + tolerance):
        return None
    t = _clamp_unit(t)
    u = _clamp_unit(u)
    return LineIntersection2((p[0] + r[0] * t, p[1] + r[1] * t), t, u)


def _line3_line3_intersection(
    left: Line3Points,
    right: Line3Points,
    *,
    tolerance: float = 1e-9,
) -> LineIntersection3 | None:
    """Return the unique intersection between two bounded 3D segments."""
    result = closest_points_between_segments3(left, right, tolerance=tolerance)
    if result.distance > tolerance:
        return None
    point = (
        (result.left[0] + result.right[0]) * 0.5,
        (result.left[1] + result.right[1]) * 0.5,
        (result.left[2] + result.right[2]) * 0.5,
    )
    return LineIntersection3(point, result.left_parameter, result.right_parameter)


def _line3_plane_intersection(
    line: Line3Points,
    origin: Point3,
    normal: Point3,
    *,
    tolerance: float = 1e-9,
    bounded: bool = True,
) -> LinePlaneIntersection | None:
    """Return a line/plane intersection, or ``None`` for parallel/no segment hit."""
    tolerance = positive_tolerance(tolerance)
    start, end = line
    direction = sub3(end, start)
    denominator = dot3(normal, direction)
    if abs(denominator) <= tolerance:
        return None
    t = dot3(normal, sub3(origin, start)) / denominator
    if bounded and not (-tolerance <= t <= 1.0 + tolerance):
        return None
    t = _clamp_unit(t) if bounded else t
    return LinePlaneIntersection(_lerp3(start, end, t), t)


def _plane_plane_intersection(
    left_origin: Point3,
    left_normal: Point3,
    right_origin: Point3,
    right_normal: Point3,
    *,
    tolerance: float = 1e-9,
) -> InfiniteLine3 | None:
    """Return the infinite line where two planes meet."""
    tolerance = positive_tolerance(tolerance)
    left_unit = _normalised3(left_normal, "left_normal")
    right_unit = _normalised3(right_normal, "right_normal")
    direction = cross3(left_unit, right_unit)
    direction_length_sq = dot3(direction, direction)
    if direction_length_sq <= tolerance * tolerance:
        return None

    left_d = dot3(left_unit, left_origin)
    right_d = dot3(right_unit, right_origin)
    numerator = cross3(
        (
            left_d * right_unit[0] - right_d * left_unit[0],
            left_d * right_unit[1] - right_d * left_unit[1],
            left_d * right_unit[2] - right_d * left_unit[2],
        ),
        direction,
    )
    point = scale3(numerator, 1.0 / direction_length_sq)
    return InfiniteLine3(point, _normalised3(direction, "direction"))


def _surface_plane(value: object) -> tuple[Point3, Point3] | None:
    base_plane = getattr(value, "base_plane", None)
    kind = getattr(value, "kind", None)
    if kind != "plane" or base_plane is None:
        return None
    return plane_origin_normal(base_plane)


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


def _cross2(left: Point2, right: Point2) -> float:
    return left[0] * right[1] - left[1] * right[0]


def _lerp3(start: Point3, end: Point3, parameter: float) -> Point3:
    return (
        start[0] + (end[0] - start[0]) * parameter,
        start[1] + (end[1] - start[1]) * parameter,
        start[2] + (end[2] - start[2]) * parameter,
    )


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, value))


__all__ = [
    "InfiniteLine3",
    "LineIntersection2",
    "LineIntersection3",
    "LinePlaneIntersection",
    "intersection",
]
