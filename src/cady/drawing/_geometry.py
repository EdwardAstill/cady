"""Shared 2D coercion and bounds helpers for drawing modules."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol, TypeAlias, cast, runtime_checkable

Point2: TypeAlias = tuple[float, float]
Bounds2: TypeAlias = tuple[Point2, Point2]


@runtime_checkable
class Bounded2(Protocol):
    def bounds(self) -> object: ...


@runtime_checkable
class ArrayConvertible2(Protocol):
    def to_array(self, *, tolerance: float) -> object: ...


def bounds2(value: object, *, name: str = "bounds") -> Bounds2:
    """Return a pair of 2D bounds tuples."""
    if isinstance(value, Sequence):
        sequence = cast(Sequence[object], value)
        if len(sequence) == 2:
            return cast(Bounds2, (sequence[0], sequence[1]))
    raise TypeError(f"{name} must be a pair of 2D points")


def points_bounds(points: Iterable[object], *, name: str = "points") -> Bounds2:
    """Return axis-aligned bounds for a non-empty point collection."""
    converted = tuple(cast(Point2, point) for point in points)
    if not converted:
        raise ValueError(f"{name} must contain at least one point")
    min_x = min(point[0] for point in converted)
    min_y = min(point[1] for point in converted)
    max_x = max(point[0] for point in converted)
    max_y = max(point[1] for point in converted)
    return (min_x, min_y), (max_x, max_y)


def merge_bounds(bounds: Iterable[Bounds2]) -> Bounds2:
    """Return a single bounds box spanning all supplied bounds."""
    items = tuple(bounds)
    if not items:
        raise ValueError("cannot calculate bounds for an empty drawing")
    min_x = min(item[0][0] for item in items)
    min_y = min(item[0][1] for item in items)
    max_x = max(item[1][0] for item in items)
    max_y = max(item[1][1] for item in items)
    return (min_x, min_y), (max_x, max_y)


def geometry_bounds(geometry: object) -> Bounds2:
    """Extract bounds from a geometry object via ``bounds`` or ``points``."""
    raw_bounds = getattr(geometry, "bounds", None)
    if callable(raw_bounds):
        return bounds2(raw_bounds(), name="geometry bounds")
    if raw_bounds is not None:
        return bounds2(raw_bounds, name="geometry bounds")

    raw_points = getattr(geometry, "points", None)
    points = raw_points() if callable(raw_points) else raw_points
    if isinstance(points, Iterable):
        return points_bounds(cast(Iterable[object], points), name="geometry points")

    raise TypeError("geometry must provide bounds or points")


def transformed_bounds(
    bounds: Bounds2,
    *,
    at: Point2,
    scale: float = 1.0,
    rotation: float = 0.0,
) -> Bounds2:
    """Transform axis-aligned bounds by scale, rotation, and translation."""
    import math

    (min_x, min_y), (max_x, max_y) = bounds
    corners = (
        (min_x, min_y),
        (min_x, max_y),
        (max_x, min_y),
        (max_x, max_y),
    )
    cos_r = math.cos(rotation)
    sin_r = math.sin(rotation)
    transformed: list[Point2] = []
    for x, y in corners:
        sx = x * scale
        sy = y * scale
        transformed.append((at[0] + sx * cos_r - sy * sin_r, at[1] + sx * sin_r + sy * cos_r))
    return points_bounds(transformed, name="transformed bounds")
