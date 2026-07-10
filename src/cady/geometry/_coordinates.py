"""Private conversion helpers for tuple-backed point values."""

from __future__ import annotations

from collections.abc import Iterable
from math import isfinite
from typing import TypeAlias, cast

Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]


def point2(value: object, *, name: str = "point") -> Point2:
    return cast(Point2, _coordinates(value, expected=2, name=name))


def point3(value: object, *, name: str = "point") -> Point3:
    return cast(Point3, _coordinates(value, expected=3, name=name))


def _coordinates(value: object, *, expected: int, name: str) -> tuple[float, ...]:
    if isinstance(value, str | bytes) or not isinstance(value, Iterable):
        raise TypeError(f"{name} must contain {expected} coordinates")
    values = tuple(cast(Iterable[object], value))
    if len(values) != expected:
        raise ValueError(f"{name} must contain {expected} coordinates")

    try:
        coordinates = tuple(
            float(component)  # type: ignore[arg-type]
            for component in values
        )
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} coordinates must be real numbers") from exc
    if not all(isfinite(component) for component in coordinates):
        raise ValueError(f"{name} coordinates must be finite")
    return coordinates
