"""Closed circular and elliptical 2D curve geometry."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, pi, sin
from typing import TYPE_CHECKING

from cady.geometry.curves2 import Point2Like, polygon_array, validate_tolerance
from cady.operations.sampling2 import circle_points, segments_for_circle
from cady.utils import finite, positive
from cady.vec import Vec2, promote2

if TYPE_CHECKING:
    from cady.operations import ArrayPolygon2


@dataclass(frozen=True, slots=True, init=False)
class Circle2:
    """Closed circular 2D curve."""

    centre: Vec2
    radius: float

    def __init__(self, centre: Point2Like, radius: float) -> None:
        object.__setattr__(self, "centre", promote2(centre))
        object.__setattr__(self, "radius", positive(radius, "radius"))

    def bounds(self) -> tuple[Vec2, Vec2]:
        return (
            Vec2(self.centre.x - self.radius, self.centre.y - self.radius),
            Vec2(self.centre.x + self.radius, self.centre.y + self.radius),
        )

    def points(self) -> tuple[Vec2, ...]:
        point = Vec2(self.centre.x + self.radius, self.centre.y)
        return (point, point)

    def to_array(self, *, tolerance: float) -> ArrayPolygon2:
        tolerance = validate_tolerance(tolerance)
        return polygon_array(
            tuple(
                Vec2(x, y)
                for x, y in circle_points(
                    self.centre.tuple(),
                    self.radius,
                    tolerance=tolerance,
                )
            )
        )


@dataclass(frozen=True, slots=True, init=False)
class Ellipse2:
    """Closed elliptical 2D curve with optional rotation."""

    centre: Vec2
    radius_x: float
    radius_y: float
    rotation_rad: float = 0.0

    def __init__(
        self,
        centre: Point2Like,
        radius_x: float,
        radius_y: float,
        rotation_rad: float = 0.0,
    ) -> None:
        object.__setattr__(self, "centre", promote2(centre))
        object.__setattr__(self, "radius_x", positive(radius_x, "radius_x"))
        object.__setattr__(self, "radius_y", positive(radius_y, "radius_y"))
        object.__setattr__(self, "rotation_rad", finite(rotation_rad, "rotation_rad"))

    def _sample_points(self, *, tolerance: float) -> tuple[Vec2, ...]:
        count = segments_for_circle(max(self.radius_x, self.radius_y), tolerance)
        cr = cos(self.rotation_rad)
        sr = sin(self.rotation_rad)
        points: list[Vec2] = []
        for index in range(count):
            angle = 2.0 * pi * index / count
            x = self.radius_x * cos(angle)
            y = self.radius_y * sin(angle)
            points.append(Vec2(self.centre.x + x * cr - y * sr, self.centre.y + x * sr + y * cr))
        return tuple(points)

    def bounds(self) -> tuple[Vec2, Vec2]:
        cr = cos(self.rotation_rad)
        sr = sin(self.rotation_rad)
        half_width = ((self.radius_x * cr) ** 2 + (self.radius_y * sr) ** 2) ** 0.5
        half_height = ((self.radius_x * sr) ** 2 + (self.radius_y * cr) ** 2) ** 0.5
        return (
            Vec2(self.centre.x - half_width, self.centre.y - half_height),
            Vec2(self.centre.x + half_width, self.centre.y + half_height),
        )

    def points(self) -> tuple[Vec2, ...]:
        cr = cos(self.rotation_rad)
        sr = sin(self.rotation_rad)
        start = Vec2(self.centre.x + self.radius_x * cr, self.centre.y + self.radius_x * sr)
        return (start, start)

    def to_array(self, *, tolerance: float) -> ArrayPolygon2:
        tolerance = validate_tolerance(tolerance)
        return polygon_array(self._sample_points(tolerance=tolerance))


__all__ = ["Circle2", "Ellipse2"]
