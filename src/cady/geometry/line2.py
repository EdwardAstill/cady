"""Straight 2D line segment geometry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from cady.geometry.curves2 import (
    Point2Like,
    bounds_from_points,
    polyline_array,
    validate_tolerance,
)
from cady.vec import Vec2, promote2

if TYPE_CHECKING:
    from cady.operations import ArrayPolyline2


@dataclass(frozen=True, slots=True, init=False)
class Line2:
    """Straight 2D segment between two distinct points."""

    start: Vec2
    end: Vec2

    def __init__(self, start: Point2Like, end: Point2Like) -> None:
        start = promote2(start)
        end = promote2(end)
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        if start == end:
            raise ValueError("Line2 endpoints must differ")

    def bounds(self) -> tuple[Vec2, Vec2]:
        return bounds_from_points((self.start, self.end))

    def points(self) -> tuple[Vec2, ...]:
        return (self.start, self.end)

    def to_array(self, *, tolerance: float) -> ArrayPolyline2:
        validate_tolerance(tolerance)
        return polyline_array(self.points(), closed=False)


__all__ = ["Line2"]
