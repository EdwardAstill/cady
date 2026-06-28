"""Small validation and topology helpers shared across modules."""

from __future__ import annotations

from math import isfinite

EdgeIndex = tuple[int, int]


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
