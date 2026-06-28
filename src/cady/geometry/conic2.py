"""Closed circular and elliptical 2D curve geometry."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, pi, sin
from typing import TYPE_CHECKING, TypeAlias

from cady.operations.sampling import circle_points, segments_for_circle
from cady.utils import finite, positive, positive_tolerance

Point2: TypeAlias = tuple[float, float]

if TYPE_CHECKING:
    from cady.operations.arrays import PointArray2


@dataclass(frozen=True, slots=True, init=False)
class Circle2:
    """Closed circular 2D curve."""

    centre: Point2
    radius: float

    def __init__(self, centre: Point2, radius: float) -> None:
        object.__setattr__(self, "centre", centre)
        object.__setattr__(self, "radius", positive(radius, "radius"))

    def bounds(self) -> tuple[Point2, Point2]:
        return (
            (self.centre[0] - self.radius, self.centre[1] - self.radius),
            (self.centre[0] + self.radius, self.centre[1] + self.radius),
        )

    @property
    def boundary(self) -> tuple[Point2, Point2]:
        return self.bounds()

    def points(self) -> tuple[Point2, ...]:
        point = (self.centre[0] + self.radius, self.centre[1])
        return (point, point)

    @property
    def closed(self) -> bool:
        return True

    def to_array(self, *, tolerance: float) -> PointArray2:
        tolerance = positive_tolerance(tolerance)
        from cady.operations.arrays import as_points2

        points = tuple(
            (x, y)
            for x, y in circle_points(
                self.centre,
                self.radius,
                tolerance=tolerance,
            )
        )
        return as_points2(points, name="vertices")


@dataclass(frozen=True, slots=True, init=False)
class Ellipse2:
    """Closed elliptical 2D curve with optional rotation."""

    centre: Point2
    radius_x: float
    radius_y: float
    rotation_rad: float = 0.0

    def __init__(
        self,
        centre: Point2,
        radius_x: float,
        radius_y: float,
        rotation_rad: float = 0.0,
    ) -> None:
        object.__setattr__(self, "centre", centre)
        object.__setattr__(self, "radius_x", positive(radius_x, "radius_x"))
        object.__setattr__(self, "radius_y", positive(radius_y, "radius_y"))
        object.__setattr__(self, "rotation_rad", finite(rotation_rad, "rotation_rad"))

    def bounds(self) -> tuple[Point2, Point2]:
        cr = cos(self.rotation_rad)
        sr = sin(self.rotation_rad)
        half_width = ((self.radius_x * cr) ** 2 + (self.radius_y * sr) ** 2) ** 0.5
        half_height = ((self.radius_x * sr) ** 2 + (self.radius_y * cr) ** 2) ** 0.5
        return (
            (self.centre[0] - half_width, self.centre[1] - half_height),
            (self.centre[0] + half_width, self.centre[1] + half_height),
        )

    @property
    def boundary(self) -> tuple[Point2, Point2]:
        return self.bounds()

    def points(self) -> tuple[Point2, ...]:
        cr = cos(self.rotation_rad)
        sr = sin(self.rotation_rad)
        start = (self.centre[0] + self.radius_x * cr, self.centre[1] + self.radius_x * sr)
        return (start, start)

    @property
    def closed(self) -> bool:
        return True

    def to_array(self, *, tolerance: float) -> PointArray2:
        tolerance = positive_tolerance(tolerance)
        from cady.operations.arrays import as_points2

        count = segments_for_circle(max(self.radius_x, self.radius_y), tolerance)
        cr = cos(self.rotation_rad)
        sr = sin(self.rotation_rad)
        points: list[Point2] = []
        for index in range(count):
            angle = 2.0 * pi * index / count
            x = self.radius_x * cos(angle)
            y = self.radius_y * sin(angle)
            points.append((self.centre[0] + x * cr - y * sr, self.centre[1] + x * sr + y * cr))
        return as_points2(tuple(points), name="vertices")


__all__ = ["Circle2", "Ellipse2"]
