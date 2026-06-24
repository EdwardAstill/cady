from __future__ import annotations

from cady.domain.base import Shape2D, Shape3D
from cady.domain.vec import Vec2, Vec3, promote2, promote3
from cady.ops import point_transforms as primitive


def translate_point2(point: Vec2, dx: float, dy: float) -> Vec2:
    return Vec2(*primitive.translate_point2(point.tuple(), dx, dy))


def rotate_point2(point: Vec2, centre: Vec2 | tuple[float, float], angle: float) -> Vec2:
    c = promote2(centre)
    return Vec2(*primitive.rotate_point2(point.tuple(), c.tuple(), angle))


def scale_point2(
    point: Vec2,
    sx: float,
    sy: float | None = None,
    centre: Vec2 | tuple[float, float] = (0.0, 0.0),
) -> Vec2:
    c = promote2(centre)
    y_scale = sx if sy is None else sy
    return Vec2(*primitive.scale_point2(point.tuple(), sx, y_scale, c.tuple()))


def mirror_point2(
    point: Vec2,
    a: Vec2 | tuple[float, float],
    b: Vec2 | tuple[float, float],
) -> Vec2:
    start = promote2(a)
    end = promote2(b)
    if start == end:
        raise ValueError("mirror axis must have two distinct points")
    return Vec2(*primitive.mirror_point2(point.tuple(), start.tuple(), end.tuple()))


def translate_point3(point: Vec3, dx: float, dy: float, dz: float) -> Vec3:
    return Vec3(*primitive.translate_point3(point.tuple(), dx, dy, dz))


def rotate_point3(
    point: Vec3,
    axis_origin: Vec3 | tuple[float, float, float],
    axis_dir: Vec3 | tuple[float, float, float],
    angle: float,
) -> Vec3:
    origin = promote3(axis_origin)
    direction = promote3(axis_dir)
    return Vec3(*primitive.rotate_point3(point.tuple(), origin.tuple(), direction.tuple(), angle))


def mirror_point3(
    point: Vec3,
    plane_origin: Vec3 | tuple[float, float, float],
    plane_normal: Vec3 | tuple[float, float, float],
) -> Vec3:
    origin = promote3(plane_origin)
    normal = promote3(plane_normal)
    return Vec3(*primitive.mirror_point3(point.tuple(), origin.tuple(), normal.tuple()))


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
