"""Straight 2D and 3D line segment geometry."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray

from cady.geometry.point import Point2, Point3, point2, point3
from cady.utils import positive_tolerance

PointArray2: TypeAlias = NDArray[np.float64]
PointArray3: TypeAlias = NDArray[np.float64]


@dataclass(frozen=True, slots=True, init=False)
class Line2:
    """Straight 2D segment between two distinct points."""

    start: Point2
    end: Point2

    def __init__(self, start: object, end: object) -> None:
        start = point2(start, name="start")
        end = point2(end, name="end")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        if start == end:
            raise ValueError("Line2 endpoints must differ")

    def bounds(self) -> tuple[Point2, Point2]:
        return (
            Point2(min(self.start.x, self.end.x), min(self.start.y, self.end.y)),
            Point2(max(self.start.x, self.end.x), max(self.start.y, self.end.y)),
        )

    @property
    def boundary(self) -> tuple[Point2, Point2]:
        return self.bounds()

    @property
    def length(self) -> float:
        dx = self.end[0] - self.start[0]
        dy = self.end[1] - self.start[1]
        return sqrt(dx * dx + dy * dy)

    def points(self) -> tuple[Point2, ...]:
        return (self.start, self.end)

    def to_array(self, *, tolerance: float) -> PointArray2:
        positive_tolerance(tolerance)

        return np.array((self.start, self.end), dtype=np.float64, copy=True)


@dataclass(frozen=True, slots=True, init=False)
class Line3:
    """Straight 3D curve segment."""

    start: Point3
    end: Point3

    def __init__(self, start: object, end: object) -> None:
        start = point3(start, name="start")
        end = point3(end, name="end")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        if start == end:
            raise ValueError("Line3 endpoints must differ")

    def bounds(self) -> tuple[Point3, Point3]:
        return (
            Point3(
                min(self.start[0], self.end[0]),
                min(self.start[1], self.end[1]),
                min(self.start[2], self.end[2]),
            ),
            Point3(
                max(self.start[0], self.end[0]),
                max(self.start[1], self.end[1]),
                max(self.start[2], self.end[2]),
            ),
        )

    @property
    def boundary(self) -> tuple[Point3, Point3]:
        return self.bounds()

    @property
    def length(self) -> float:
        dx = self.end[0] - self.start[0]
        dy = self.end[1] - self.start[1]
        dz = self.end[2] - self.start[2]
        return sqrt(dx * dx + dy * dy + dz * dz)

    def points(self) -> tuple[Point3, Point3]:
        return (self.start, self.end)

    def to_array(self, *, tolerance: float) -> PointArray3:
        positive_tolerance(tolerance)

        return np.array((self.start, self.end), dtype=np.float64, copy=True)


__all__ = [
    "Line2",
    "Line3",
]
