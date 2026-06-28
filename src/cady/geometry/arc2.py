"""Circular 2D arc geometry."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, pi, sin
from typing import TYPE_CHECKING

from cady.geometry.curves2 import (
    Point2Like,
    bounds_from_points,
    polyline_array,
    validate_tolerance,
)
from cady.operations.sampling2 import arc_points
from cady.utils import finite, positive
from cady.vec import Vec2, promote2

if TYPE_CHECKING:
    from cady.operations import ArrayPolyline2


@dataclass(frozen=True, slots=True, init=False)
class Arc2:
    """Circular 2D arc described by centre, radius, and sweep angles."""

    centre: Vec2
    radius: float
    start_rad: float
    end_rad: float

    def __init__(
        self,
        centre: Point2Like,
        radius: float,
        start_rad: float,
        end_rad: float,
    ) -> None:
        radius = positive(radius, "radius")
        start_rad = finite(start_rad, "start_rad")
        end_rad = finite(end_rad, "end_rad")
        object.__setattr__(self, "centre", promote2(centre))
        object.__setattr__(self, "radius", radius)
        object.__setattr__(self, "start_rad", start_rad)
        object.__setattr__(self, "end_rad", end_rad)
        if start_rad == end_rad:
            raise ValueError("Arc2 start and end angles must differ")

    def _point(self, angle: float) -> Vec2:
        return Vec2(
            self.centre.x + self.radius * cos(angle),
            self.centre.y + self.radius * sin(angle),
        )

    def bounds(self) -> tuple[Vec2, Vec2]:
        points = [self._point(self.start_rad), self._point(self.end_rad)]
        start = self.start_rad % (2 * pi)
        sweep = (self.end_rad - self.start_rad) % (2 * pi)
        for angle in (0.0, pi / 2.0, pi, 3.0 * pi / 2.0):
            if (angle - start) % (2 * pi) <= sweep:
                points.append(self._point(angle))
        return bounds_from_points(tuple(points))

    def points(self) -> tuple[Vec2, ...]:
        return (self._point(self.start_rad), self._point(self.end_rad))

    def to_array(self, *, tolerance: float) -> ArrayPolyline2:
        tolerance = validate_tolerance(tolerance)
        points = tuple(
            Vec2(x, y)
            for x, y in arc_points(
                self.centre.tuple(),
                self.radius,
                self.start_rad,
                self.end_rad,
                tolerance=tolerance,
            )
        )
        return polyline_array(points, closed=False)


__all__ = ["Arc2"]
