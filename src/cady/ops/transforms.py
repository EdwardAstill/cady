from __future__ import annotations

from math import cos, sin

from cady.domain.base import Shape2D, Shape3D
from cady.domain.vec import Vec2, Vec3, promote2, promote3


def translate_point2(point: Vec2, dx: float, dy: float) -> Vec2:
    return point + Vec2(dx, dy)


def rotate_point2(point: Vec2, centre: Vec2 | tuple[float, float], angle: float) -> Vec2:
    c = promote2(centre)
    ca = cos(angle)
    sa = sin(angle)
    rel = point - c
    return Vec2(c.x + rel.x * ca - rel.y * sa, c.y + rel.x * sa + rel.y * ca)


def scale_point2(
    point: Vec2,
    sx: float,
    sy: float | None = None,
    centre: Vec2 | tuple[float, float] = (0.0, 0.0),
) -> Vec2:
    c = promote2(centre)
    y_scale = sx if sy is None else sy
    return Vec2(c.x + (point.x - c.x) * sx, c.y + (point.y - c.y) * y_scale)


def mirror_point2(
    point: Vec2,
    a: Vec2 | tuple[float, float],
    b: Vec2 | tuple[float, float],
) -> Vec2:
    start = promote2(a)
    end = promote2(b)
    if start == end:
        raise ValueError("mirror axis must have two distinct points")
    axis = (end - start).normalised()
    rel = point - start
    projected = start + axis * rel.dot(axis)
    return projected * 2 - point


def translate_point3(point: Vec3, dx: float, dy: float, dz: float) -> Vec3:
    return point + Vec3(dx, dy, dz)


def rotate_point3(
    point: Vec3,
    axis_origin: Vec3 | tuple[float, float, float],
    axis_dir: Vec3 | tuple[float, float, float],
    angle: float,
) -> Vec3:
    origin = promote3(axis_origin)
    direction = promote3(axis_dir).normalised()
    ca = cos(angle)
    sa = sin(angle)
    rel = point - origin
    return (
        origin
        + rel * ca
        + direction.cross(rel) * sa
        + direction * (direction.dot(rel) * (1 - ca))
    )


def mirror_point3(
    point: Vec3,
    plane_origin: Vec3 | tuple[float, float, float],
    plane_normal: Vec3 | tuple[float, float, float],
) -> Vec3:
    origin = promote3(plane_origin)
    normal = promote3(plane_normal).normalised()
    return point - normal * (2 * (point - origin).dot(normal))


def translate2(shape: Shape2D, dx: float, dy: float) -> Shape2D:
    return shape.map_points(lambda point: translate_point2(point, dx, dy))


def rotate2(shape: Shape2D, centre: Vec2 | tuple[float, float], angle: float) -> Shape2D:
    return shape.map_points(lambda point: rotate_point2(point, centre, angle))


def scale2(
    shape: Shape2D,
    sx: float,
    sy: float | None = None,
    centre: Vec2 | tuple[float, float] = (0.0, 0.0),
) -> Shape2D:
    return shape.map_points(lambda point: scale_point2(point, sx, sy, centre))


def mirror2(shape: Shape2D, through: Shape2D) -> Shape2D:
    points = through.points()
    if len(points) < 2 or points[0] == points[-1]:
        raise ValueError("mirror axis must have two distinct points")
    return shape.map_points(lambda point: mirror_point2(point, points[0], points[-1]))


def translate3(shape: Shape3D, dx: float, dy: float, dz: float) -> Shape3D:
    return shape.map_points(lambda point: translate_point3(point, dx, dy, dz))


def rotate3(
    shape: Shape3D,
    axis_origin: Vec3 | tuple[float, float, float],
    axis_dir: Vec3 | tuple[float, float, float],
    angle: float,
) -> Shape3D:
    return shape.map_points(lambda point: rotate_point3(point, axis_origin, axis_dir, angle))


def mirror3(
    shape: Shape3D,
    plane_origin: Vec3 | tuple[float, float, float],
    plane_normal: Vec3 | tuple[float, float, float],
) -> Shape3D:
    return shape.map_points(lambda point: mirror_point3(point, plane_origin, plane_normal))
