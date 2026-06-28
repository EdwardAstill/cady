"""Sampling helpers for common analytic 2D curves."""

from __future__ import annotations

from math import acos, ceil, cos, pi, sin, sqrt
from typing import TypeAlias

from cady.operations.coordinates import normalised2, scale2

Point2: TypeAlias = tuple[float, float]


def segments_for_circle(radius: float, tolerance: float) -> int:
    """Estimate a polygon segment count that stays within a chord error."""
    tolerance = max(float(tolerance), 1e-9)
    if tolerance >= radius:
        return 12
    angle = 2 * acos(max(-1.0, min(1.0, 1 - tolerance / radius)))
    return max(12, ceil((2 * pi) / angle))


def circle_points(centre: Point2, radius: float, *, tolerance: float) -> tuple[Point2, ...]:
    """Sample a full circle as evenly spaced points."""
    n = segments_for_circle(radius, tolerance)
    cx, cy = centre
    return tuple(
        (cx + radius * cos(2 * pi * i / n), cy + radius * sin(2 * pi * i / n))
        for i in range(n)
    )


def arc_points(
    centre: Point2,
    radius: float,
    start_rad: float,
    end_rad: float,
    *,
    tolerance: float,
) -> tuple[Point2, ...]:
    """Sample a circular arc, including both endpoints."""
    sweep = end_rad - start_rad
    n = max(2, ceil(abs(sweep) / (2 * pi) * segments_for_circle(radius, tolerance)))
    cx, cy = centre
    return tuple(
        (
            cx + radius * cos(start_rad + sweep * i / n),
            cy + radius * sin(start_rad + sweep * i / n),
        )
        for i in range(n + 1)
    )


def cubic_bezier_points(
    control_points: tuple[Point2, ...],
    *,
    tolerance: float,
) -> tuple[Point2, ...]:
    """Sample one or more chained cubic Bezier segments."""
    pts: list[Point2] = []
    samples = max(8, ceil(1 / sqrt(tolerance)))
    for start in range(0, len(control_points) - 1, 3):
        p0, p1, p2, p3 = control_points[start : start + 4]
        for i in range(samples + 1):
            if pts and i == 0:
                continue
            t = i / samples
            u = 1 - t
            pts.append(
                (
                    p0[0] * (u**3)
                    + p1[0] * (3 * u * u * t)
                    + p2[0] * (3 * u * t * t)
                    + p3[0] * (t**3),
                    p0[1] * (u**3)
                    + p1[1] * (3 * u * u * t)
                    + p2[1] * (3 * u * t * t)
                    + p3[1] * (t**3),
                )
            )
    return tuple(pts)


def midpoint(a: Point2, b: Point2) -> Point2:
    """Return the midpoint between two 2D points."""
    return ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5)


def perpendicular(vector: Point2) -> Point2:
    """Return a unit-length left-hand perpendicular vector."""
    unit = normalised2(vector)
    return (-unit[1], unit[0])


def offset_point(
    point: Point2,
    direction: Point2,
    distance: float,
) -> Point2:
    """Offset a point along the perpendicular to ``direction``."""
    unit = perpendicular(direction)
    offset = scale2(unit, float(distance))
    return (point[0] + offset[0], point[1] + offset[1])
