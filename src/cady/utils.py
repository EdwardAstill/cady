"""Small validation and topology helpers shared across modules."""

from __future__ import annotations

from collections.abc import Iterable
from math import isfinite
from numbers import Real
from typing import cast

EdgeIndex = tuple[int, int]


def finite_coordinates(value: object, *, expected: int, name: str) -> tuple[float, ...]:
    """Return a fixed-length tuple of finite real coordinates."""
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


def finite(value: float, name: str) -> float:
    """Return ``value`` as a finite float or raise ``ValueError``."""
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def positive(value: float, name: str) -> float:
    """Return ``value`` as a positive finite float."""
    value = finite(value, name)
    if value <= 0.0:
        raise ValueError(f"{name} must be positive")
    return value


def positive_tolerance(tolerance: float) -> float:
    """Validate a positive tolerance value."""
    return positive(tolerance, "tolerance")


def loop_edges(count: int) -> tuple[EdgeIndex, ...]:
    """Return closed-loop edges for ``count`` ordered vertices."""
    return tuple((index, (index + 1) % count) for index in range(count))


__all__ = ["EdgeIndex", "finite", "loop_edges", "positive", "positive_tolerance"]
