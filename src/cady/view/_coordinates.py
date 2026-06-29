"""Small coordinate coercion helpers for view values."""

from __future__ import annotations

from collections.abc import Iterable
from math import isfinite
from typing import Any, TypeAlias, cast

from cady.view.errors import ViewError

Point3: TypeAlias = tuple[float, float, float]


def finite_point3(value: object, *, name: str = "point") -> Point3:
    """Coerce a tuple-like value into a finite 3D point."""
    as_tuple = getattr(value, "tuple", None)
    raw = as_tuple() if callable(as_tuple) else value
    try:
        point = tuple(float(component) for component in cast(Iterable[Any], raw))
    except (TypeError, ValueError) as exc:
        raise ViewError(f"{name} must be a finite 3D coordinate") from exc
    if len(point) != 3 or any(not isfinite(component) for component in point):
        raise ViewError(f"{name} must be a finite 3D coordinate")
    return (point[0], point[1], point[2])


__all__ = ["Point3", "finite_point3"]
