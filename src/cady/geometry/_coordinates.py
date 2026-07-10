"""Private conversion helpers for affine coordinate values."""

from __future__ import annotations

from collections.abc import Iterable
from math import isfinite
from numbers import Real
from typing import TYPE_CHECKING, cast


def point2(value: object, *, name: str = "point") -> Point2:
    from cady.geometry.point import Point2

    if isinstance(value, Point2):
        return value
    x, y = finite_coordinates(value, expected=2, name=name)
    return Point2(x, y)


def point3(value: object, *, name: str = "point") -> Point3:
    from cady.geometry.point import Point3

    if isinstance(value, Point3):
        return value
    x, y, z = finite_coordinates(value, expected=3, name=name)
    return Point3(x, y, z)


def vector2(value: object, *, name: str = "vector") -> Vector2:
    from cady.geometry.vector import Vector2

    if isinstance(value, Vector2):
        return value
    x, y = finite_coordinates(value, expected=2, name=name)
    return Vector2(x, y)


def vector3(value: object, *, name: str = "vector") -> Vector3:
    from cady.geometry.vector import Vector3

    if isinstance(value, Vector3):
        return value
    x, y, z = finite_coordinates(value, expected=3, name=name)
    return Vector3(x, y, z)


def finite_coordinates(value: object, *, expected: int, name: str) -> tuple[float, ...]:
    if isinstance(value, str | bytes) or not isinstance(value, Iterable):
        raise TypeError(f"{name} must contain {expected} coordinates")
    values = tuple(cast(Iterable[object], value))
    if len(values) != expected:
        raise ValueError(f"{name} must contain {expected} coordinates")
    if any(isinstance(component, bool) for component in values) or any(
        not isinstance(component, Real) for component in values
    ):
        raise TypeError(f"{name} coordinates must be real numbers")

    numeric_values = cast(tuple[Real, ...], values)
    coordinates = tuple(float(component) for component in numeric_values)
    if not all(isfinite(component) for component in coordinates):
        raise ValueError(f"{name} coordinates must be finite")
    return coordinates


if TYPE_CHECKING:
    from cady.geometry.point import Point2, Point3
    from cady.geometry.vector import Vector2, Vector3
