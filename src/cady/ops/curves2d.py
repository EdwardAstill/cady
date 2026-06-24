from __future__ import annotations

from math import acos, ceil, cos, pi, sin, sqrt
from typing import TypeAlias

Point2: TypeAlias = tuple[float, float]


def segments_for_circle(radius: float, tolerance: float) -> int:
    tolerance = max(float(tolerance), 1e-9)
    if tolerance >= radius:
        return 12
    angle = 2 * acos(max(-1.0, min(1.0, 1 - tolerance / radius)))
    return max(12, ceil((2 * pi) / angle))


def circle_points(centre: Point2, radius: float, *, tolerance: float) -> tuple[Point2, ...]:
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
