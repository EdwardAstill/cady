"""Cubic Bezier spline geometry in 2D and 3D."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import ceil, sqrt
from typing import TYPE_CHECKING, TypeAlias

import numpy as np
from numpy.typing import NDArray

from cady.operations.coordinates import cross3, length3, scale3, sub3
from cady.utils import positive_tolerance

Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]
PointArray2: TypeAlias = NDArray[np.float64]
PointArray3: TypeAlias = NDArray[np.float64]

if TYPE_CHECKING:
    from cady.geometry.polyline import Polyline2


def _append_unique_point(points: list[Point3], point: Point3) -> None:
    if not points or points[-1] != point:
        points.append(point)


def _append_unique_point2(points: list[Point2], point: Point2) -> None:
    if not points or points[-1] != point:
        points.append(point)


@dataclass(frozen=True, slots=True, init=False)
class Spline2:
    """Cubic Bezier spline made from 3n+1 2D control points."""

    control_points: tuple[Point2, ...]
    closed: bool = False

    def __init__(self, control_points: tuple[Point2, ...], closed: bool = False) -> None:
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

    def points(self) -> tuple[Point2, ...]:
        if self.closed and self.control_points[0] != self.control_points[-1]:
            return self.control_points + (self.control_points[0],)
        return self.control_points

    def to_array(self, *, tolerance: float) -> PointArray2:
        tolerance = positive_tolerance(tolerance)

        points = _cubic_bezier_points2(self.control_points, tolerance=tolerance)
        if self.closed and points[0] != points[-1]:
            points = (*points, points[0])
        return np.array(points, dtype=np.float64, copy=True)

    def discretise(self, *, tolerance: float) -> Polyline2:
        from cady.geometry.polyline import Polyline2

        points = tuple((float(x), float(y)) for x, y in self.to_array(tolerance=tolerance))
        return Polyline2(points, closed=self.closed)

    def discretize(self, *, tolerance: float) -> Polyline2:
        return self.discretise(tolerance=tolerance)


@dataclass(frozen=True, slots=True, init=False)
class Spline3:
    """Cubic Bezier spline made from 3n+1 3D control points."""

    control_points: tuple[Point3, ...]

    def __init__(self, control_points: Iterable[Point3]) -> None:
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

    def points(self) -> tuple[Point3, ...]:
        return self.control_points

    def to_array(self, *, tolerance: float) -> PointArray3:
        tolerance = positive_tolerance(tolerance)
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
        return np.array(points, dtype=np.float64, copy=True)


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
    return scale3((left[0] + right[0], left[1] + right[1], left[2] + right[2]), 0.5)


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
