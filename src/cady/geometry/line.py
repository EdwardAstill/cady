"""Straight 2D and 3D line segment geometry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

from cady.utils import positive_tolerance

Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]

if TYPE_CHECKING:
    from cady.operations.arrays import PointArray2, PointArray3


@dataclass(frozen=True, slots=True, init=False)
class Line2:
    """Straight 2D segment between two distinct points."""

    start: Point2
    end: Point2

    def __init__(self, start: Point2, end: Point2) -> None:
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        if start == end:
            raise ValueError("Line2 endpoints must differ")

    def bounds(self) -> tuple[Point2, Point2]:
        return (
            (min(self.start[0], self.end[0]), min(self.start[1], self.end[1])),
            (max(self.start[0], self.end[0]), max(self.start[1], self.end[1])),
        )

    @property
    def boundary(self) -> tuple[Point2, Point2]:
        return self.bounds()

    def points(self) -> tuple[Point2, ...]:
        return (self.start, self.end)

    def to_array(self, *, tolerance: float) -> PointArray2:
        positive_tolerance(tolerance)
        from cady.operations.arrays import as_points2

        return as_points2((self.start, self.end), name="vertices")


@dataclass(frozen=True, slots=True, init=False)
class Line3:
    """Straight 3D curve segment."""

    start: Point3
    end: Point3

    def __init__(self, start: Point3, end: Point3) -> None:
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        if start == end:
            raise ValueError("Line3 endpoints must differ")

    def bounds(self) -> tuple[Point3, Point3]:
        return (
            (
                min(self.start[0], self.end[0]),
                min(self.start[1], self.end[1]),
                min(self.start[2], self.end[2]),
            ),
            (
                max(self.start[0], self.end[0]),
                max(self.start[1], self.end[1]),
                max(self.start[2], self.end[2]),
            ),
        )

    @property
    def boundary(self) -> tuple[Point3, Point3]:
        return self.bounds()

    def points(self) -> tuple[Point3, Point3]:
        return (self.start, self.end)

    def to_array(self, *, tolerance: float) -> PointArray3:
        positive_tolerance(tolerance)

        from cady.operations.arrays import as_points3

        return as_points3((self.start, self.end), name="vertices")


__all__ = [
    "Line2",
    "Line3",
]
