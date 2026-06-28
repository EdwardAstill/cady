"""Cubic Bezier spline geometry in 2D."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from cady.geometry.curves2 import (
    Point2Like,
    bounds_from_points,
    point_tuples,
    validate_tolerance,
)
from cady.vec import Vec2, promote2

if TYPE_CHECKING:
    from cady.operations import ArrayPolyline2


@dataclass(frozen=True, slots=True, init=False)
class Spline2:
    """Cubic Bezier spline made from 3n+1 2D control points."""

    control_points: tuple[Vec2, ...]
    closed: bool = False

    def __init__(self, control_points: tuple[Point2Like, ...], closed: bool = False) -> None:
        points = tuple(promote2(point) for point in control_points)
        object.__setattr__(self, "control_points", points)
        object.__setattr__(self, "closed", bool(closed))
        if len(points) < 4 or (len(points) - 1) % 3 != 0:
            raise ValueError("Spline2 requires 3n+1 cubic Bezier control points")

    def bounds(self) -> tuple[Vec2, Vec2]:
        return bounds_from_points(self.control_points)

    def points(self) -> tuple[Vec2, ...]:
        if self.closed and self.control_points[0] != self.control_points[-1]:
            return self.control_points + (self.control_points[0],)
        return self.control_points

    def to_array(self, *, tolerance: float) -> ArrayPolyline2:
        tolerance = validate_tolerance(tolerance)
        from cady.operations import ArrayBezierSpline2
        from cady.operations.validation import as_points2

        spline = ArrayBezierSpline2(
            as_points2(point_tuples(self.control_points), name="control_points"),
            closed=self.closed,
        )
        return spline.sample(tolerance=tolerance)


__all__ = ["Spline2"]
