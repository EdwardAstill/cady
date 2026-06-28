"""Small profile-construction vector helpers."""

from __future__ import annotations

from cady.vec import Vec2, promote2


def midpoint(a: Vec2 | tuple[float, float], b: Vec2 | tuple[float, float]) -> Vec2:
    """Return the midpoint between two 2D points."""
    left = promote2(a)
    right = promote2(b)
    return Vec2((left.x + right.x) * 0.5, (left.y + right.y) * 0.5)


def perpendicular(vector: Vec2 | tuple[float, float]) -> Vec2:
    """Return a unit-length left-hand perpendicular vector."""
    direction = promote2(vector)
    if direction.length() == 0:
        raise ValueError("cannot compute perpendicular for zero Vec2")
    unit = direction.normalised()
    return Vec2(-unit.y, unit.x)


def offset_point(
    point: Vec2 | tuple[float, float],
    direction: Vec2 | tuple[float, float],
    distance: float,
) -> Vec2:
    """Offset a point along the perpendicular to ``direction``."""
    origin = promote2(point)
    unit = perpendicular(direction)
    return origin + unit * float(distance)


__all__ = [
    "midpoint",
    "offset_point",
    "perpendicular",
]
