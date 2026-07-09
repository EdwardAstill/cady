"""Closed circular and elliptical 2D curve geometry."""

from __future__ import annotations

from dataclasses import dataclass
from math import acos, ceil, cos, pi, sin, sqrt
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray

from cady.geometry.point import Point2
from cady.utils import finite, positive, positive_tolerance

PointArray2: TypeAlias = NDArray[np.float64]


def _segments_for_circle(radius: float, tolerance: float) -> int:
    tolerance = max(float(tolerance), 1e-9)
    if tolerance >= radius:
        return 12
    angle = 2.0 * acos(max(-1.0, min(1.0, 1.0 - tolerance / radius)))
    return max(12, ceil((2.0 * pi) / angle))


@dataclass(frozen=True, slots=True, init=False)
class Circle2:
    """Closed circular 2D curve."""

    center: Point2
    radius: float

    def __init__(self, center: object, radius: float) -> None:
        object.__setattr__(self, "center", Point2(center))
        object.__setattr__(self, "radius", positive(radius, "radius"))

    def bounds(self) -> tuple[Point2, Point2]:
        return (
            Point2(self.center[0] - self.radius, self.center[1] - self.radius),
            Point2(self.center[0] + self.radius, self.center[1] + self.radius),
        )

    @property
    def boundary(self) -> tuple[Point2, Point2]:
        return self.bounds()

    @property
    def length(self) -> float:
        return 2.0 * pi * self.radius

    def points(self) -> tuple[Point2, ...]:
        point = Point2(self.center[0] + self.radius, self.center[1])
        return (point, point)

    @property
    def closed(self) -> bool:
        return True

    def to_array(self, *, tolerance: float) -> PointArray2:
        tolerance = positive_tolerance(tolerance)

        count = _segments_for_circle(self.radius, tolerance)
        cx, cy = self.center
        points = tuple(
            (
                cx + self.radius * cos(2.0 * pi * index / count),
                cy + self.radius * sin(2.0 * pi * index / count),
            )
            for index in range(count)
        )
        return np.array(points, dtype=np.float64, copy=True)


@dataclass(frozen=True, slots=True, init=False)
class Ellipse2:
    """Closed elliptical 2D curve with optional rotation."""

    center: Point2
    radius_x: float
    radius_y: float
    rotation_rad: float = 0.0

    def __init__(
        self,
        center: object,
        radius_x: float,
        radius_y: float,
        rotation_rad: float = 0.0,
    ) -> None:
        object.__setattr__(self, "center", Point2(center))
        object.__setattr__(self, "radius_x", positive(radius_x, "radius_x"))
        object.__setattr__(self, "radius_y", positive(radius_y, "radius_y"))
        object.__setattr__(self, "rotation_rad", finite(rotation_rad, "rotation_rad"))

    def bounds(self) -> tuple[Point2, Point2]:
        cr = cos(self.rotation_rad)
        sr = sin(self.rotation_rad)
        half_width = ((self.radius_x * cr) ** 2 + (self.radius_y * sr) ** 2) ** 0.5
        half_height = ((self.radius_x * sr) ** 2 + (self.radius_y * cr) ** 2) ** 0.5
        return (
            Point2(self.center[0] - half_width, self.center[1] - half_height),
            Point2(self.center[0] + half_width, self.center[1] + half_height),
        )

    @property
    def boundary(self) -> tuple[Point2, Point2]:
        return self.bounds()

    @property
    def length(self) -> float:
        a = max(self.radius_x, self.radius_y)
        b = min(self.radius_x, self.radius_y)
        h = ((a - b) * (a - b)) / ((a + b) * (a + b))
        return pi * (a + b) * (1.0 + (3.0 * h) / (10.0 + sqrt(4.0 - 3.0 * h)))

    def points(self) -> tuple[Point2, ...]:
        cr = cos(self.rotation_rad)
        sr = sin(self.rotation_rad)
        start = Point2(self.center[0] + self.radius_x * cr, self.center[1] + self.radius_x * sr)
        return (start, start)

    @property
    def closed(self) -> bool:
        return True

    def to_array(self, *, tolerance: float) -> PointArray2:
        tolerance = positive_tolerance(tolerance)

        count = _segments_for_circle(max(self.radius_x, self.radius_y), tolerance)
        cr = cos(self.rotation_rad)
        sr = sin(self.rotation_rad)
        points: list[Point2] = []
        for index in range(count):
            angle = 2.0 * pi * index / count
            x = self.radius_x * cos(angle)
            y = self.radius_y * sin(angle)
            points.append(
                Point2(
                    self.center[0] + x * cr - y * sr,
                    self.center[1] + x * sr + y * cr,
                )
            )
        return np.array(tuple(points), dtype=np.float64, copy=True)


__all__ = ["Circle2", "Ellipse2"]
