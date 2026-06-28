"""Shared protocols and helpers for 2D curve value objects."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from cady.utils import positive_tolerance
from cady.vec import Vec2

if TYPE_CHECKING:
    from cady.operations import ArrayPolygon2, ArrayPolyline2

Point2Like = Vec2 | tuple[float, float]


class Curve2(Protocol):
    """Common protocol for 2D curves that can be discretised on demand."""

    def bounds(self) -> tuple[Vec2, Vec2]: ...

    def points(self) -> tuple[Vec2, ...]: ...

    def to_array(self, *, tolerance: float) -> object: ...


class ClosedCurve2(Curve2, Protocol):
    """Protocol for closed 2D curves that can produce polygon data."""

    def to_array(self, *, tolerance: float) -> ArrayPolygon2: ...


def bounds_from_points(points: tuple[Vec2, ...]) -> tuple[Vec2, Vec2]:
    if not points:
        raise ValueError("bounds require at least one point")
    return (
        Vec2(min(point.x for point in points), min(point.y for point in points)),
        Vec2(max(point.x for point in points), max(point.y for point in points)),
    )


def point_tuples(points: tuple[Vec2, ...]) -> tuple[tuple[float, float], ...]:
    return tuple(point.tuple() for point in points)


def polyline_array(points: tuple[Vec2, ...], *, closed: bool) -> ArrayPolyline2:
    from cady.operations import ArrayPolyline2
    from cady.operations.validation import as_points2

    return ArrayPolyline2(as_points2(point_tuples(points), name="vertices"), closed=closed)


def polygon_array(points: tuple[Vec2, ...]) -> ArrayPolygon2:
    from cady.operations import ArrayPolygon2
    from cady.operations.validation import as_points2

    return ArrayPolygon2(as_points2(point_tuples(dedupe_closed(points)), name="outer"))


def dedupe_closed(points: tuple[Vec2, ...]) -> tuple[Vec2, ...]:
    if len(points) > 1 and points[0] == points[-1]:
        return points[:-1]
    return points


def validate_tolerance(tolerance: float) -> float:
    return positive_tolerance(tolerance)


__all__ = [
    "ClosedCurve2",
    "Curve2",
    "Point2Like",
    "bounds_from_points",
    "dedupe_closed",
    "point_tuples",
    "polygon_array",
    "polyline_array",
    "validate_tolerance",
]
