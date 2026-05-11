from __future__ import annotations

from cad.geom.vec import Vec2, promote2


def midpoint(a: Vec2 | tuple[float, float], b: Vec2 | tuple[float, float]) -> Vec2:
    left = promote2(a)
    right = promote2(b)
    return Vec2((left.x + right.x) * 0.5, (left.y + right.y) * 0.5)


def perpendicular(vector: Vec2 | tuple[float, float]) -> Vec2:
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
    origin = promote2(point)
    unit = perpendicular(direction)
    return origin + unit * float(distance)
