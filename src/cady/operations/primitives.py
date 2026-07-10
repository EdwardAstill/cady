"""Low-level tuple coordinate primitives."""

from __future__ import annotations

from collections.abc import Sequence
from math import sqrt
from typing import TypeAlias

Coordinate2: TypeAlias = Sequence[float]
Coordinate3: TypeAlias = Sequence[float]
Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]


def add2(left: Coordinate2, right: Coordinate2) -> Point2:
    return (left[0] + right[0], left[1] + right[1])


def sub2(left: Coordinate2, right: Coordinate2) -> Point2:
    return (left[0] - right[0], left[1] - right[1])


def scale2(point: Coordinate2, scalar: float) -> Point2:
    return (point[0] * scalar, point[1] * scalar)


def dot2(left: Coordinate2, right: Coordinate2) -> float:
    return left[0] * right[0] + left[1] * right[1]


def length2(point: Coordinate2) -> float:
    return sqrt(dot2(point, point))


def distance2(left: Coordinate2, right: Coordinate2) -> float:
    return length2(sub2(left, right))


def normalised2(point: Coordinate2) -> Point2:
    length = length2(point)
    if length == 0.0:
        raise ValueError("cannot normalise zero 2D direction")
    return scale2(point, 1.0 / length)


def add3(left: Coordinate3, right: Coordinate3) -> Point3:
    return (left[0] + right[0], left[1] + right[1], left[2] + right[2])


def sub3(left: Coordinate3, right: Coordinate3) -> Point3:
    return (left[0] - right[0], left[1] - right[1], left[2] - right[2])


def scale3(point: Coordinate3, scalar: float) -> Point3:
    return (point[0] * scalar, point[1] * scalar, point[2] * scalar)


def dot3(left: Coordinate3, right: Coordinate3) -> float:
    return left[0] * right[0] + left[1] * right[1] + left[2] * right[2]


def cross3(left: Coordinate3, right: Coordinate3) -> Point3:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def length3(point: Coordinate3) -> float:
    return sqrt(dot3(point, point))


def distance3(left: Coordinate3, right: Coordinate3) -> float:
    return length3(sub3(left, right))


def normalised3(point: Coordinate3) -> Point3:
    length = length3(point)
    if length == 0.0:
        raise ValueError("cannot normalise zero 3D direction")
    return scale3(point, 1.0 / length)


def is_parallel3(left: Coordinate3, right: Coordinate3, *, tolerance: float = 1e-6) -> bool:
    cross = cross3(left, right)
    return dot3(cross, cross) < tolerance * tolerance


def project_onto_line3(
    point: Coordinate3,
    line_point: Coordinate3,
    line_dir: Coordinate3,
) -> float:
    offset = sub3(point, line_point)
    return dot3(offset, line_dir) / dot3(line_dir, line_dir)


__all__ = [
    "Point2",
    "Point3",
    "add2",
    "add3",
    "cross3",
    "distance2",
    "distance3",
    "dot2",
    "dot3",
    "is_parallel3",
    "length2",
    "length3",
    "normalised2",
    "normalised3",
    "project_onto_line3",
    "scale2",
    "scale3",
    "sub2",
    "sub3",
]
