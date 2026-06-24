from __future__ import annotations

from math import cos, sin
from typing import TypeAlias

Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]


def translate_point2(point: Point2, dx: float, dy: float) -> Point2:
    return (point[0] + dx, point[1] + dy)


def rotate_point2(point: Point2, centre: Point2, angle: float) -> Point2:
    ca = cos(angle)
    sa = sin(angle)
    rel_x = point[0] - centre[0]
    rel_y = point[1] - centre[1]
    return (centre[0] + rel_x * ca - rel_y * sa, centre[1] + rel_x * sa + rel_y * ca)


def scale_point2(point: Point2, sx: float, sy: float, centre: Point2) -> Point2:
    return (centre[0] + (point[0] - centre[0]) * sx, centre[1] + (point[1] - centre[1]) * sy)


def mirror_point2(point: Point2, a: Point2, b: Point2) -> Point2:
    axis = _normalised2((b[0] - a[0], b[1] - a[1]))
    rel = (point[0] - a[0], point[1] - a[1])
    projected = (a[0] + axis[0] * _dot2(rel, axis), a[1] + axis[1] * _dot2(rel, axis))
    return (projected[0] * 2 - point[0], projected[1] * 2 - point[1])


def translate_point3(point: Point3, dx: float, dy: float, dz: float) -> Point3:
    return (point[0] + dx, point[1] + dy, point[2] + dz)


def rotate_point3(point: Point3, axis_origin: Point3, axis_dir: Point3, angle: float) -> Point3:
    direction = _normalised3(axis_dir)
    ca = cos(angle)
    sa = sin(angle)
    rel = (point[0] - axis_origin[0], point[1] - axis_origin[1], point[2] - axis_origin[2])
    cross = _cross3(direction, rel)
    dot = _dot3(direction, rel)
    rotated = (
        rel[0] * ca + cross[0] * sa + direction[0] * (dot * (1 - ca)),
        rel[1] * ca + cross[1] * sa + direction[1] * (dot * (1 - ca)),
        rel[2] * ca + cross[2] * sa + direction[2] * (dot * (1 - ca)),
    )
    return (
        axis_origin[0] + rotated[0],
        axis_origin[1] + rotated[1],
        axis_origin[2] + rotated[2],
    )


def mirror_point3(point: Point3, plane_origin: Point3, plane_normal: Point3) -> Point3:
    normal = _normalised3(plane_normal)
    rel = (
        point[0] - plane_origin[0],
        point[1] - plane_origin[1],
        point[2] - plane_origin[2],
    )
    distance = 2 * _dot3(rel, normal)
    return (
        point[0] - normal[0] * distance,
        point[1] - normal[1] * distance,
        point[2] - normal[2] * distance,
    )


def _dot2(a: Point2, b: Point2) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _normalised2(a: Point2) -> Point2:
    length = _dot2(a, a) ** 0.5
    if length == 0:
        raise ValueError("zero-length vector")
    return (a[0] / length, a[1] / length)


def _dot3(a: Point3, b: Point3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross3(a: Point3, b: Point3) -> Point3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _normalised3(a: Point3) -> Point3:
    length = _dot3(a, a) ** 0.5
    if length == 0:
        raise ValueError("zero-length vector")
    return (a[0] / length, a[1] / length, a[2] / length)
