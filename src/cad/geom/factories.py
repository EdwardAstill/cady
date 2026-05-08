from __future__ import annotations

from cad.geom.shapes2d import Arc, Circle, Line, Polyline, Rectangle, Spline
from cad.geom.shapes3d import Prism, Sphere
from cad.geom.vec import Vec2, Vec3

Point2 = Vec2 | tuple[float, float]
Point3 = Vec3 | tuple[float, float, float]


def line(a: Point2, b: Point2) -> Line:
    return Line(Vec2.from_xy(a), Vec2.from_xy(b))


def arc(centre: Point2, radius: float, start: float, end: float) -> Arc:
    return Arc(Vec2.from_xy(centre), radius, start, end)


def circle(centre: Point2, radius: float) -> Circle:
    return Circle(Vec2.from_xy(centre), radius)


def rectangle(corner: Point2, size: Point2) -> Rectangle:
    return Rectangle(Vec2.from_xy(corner), Vec2.from_xy(size))


def polyline(points: list[Point2] | tuple[Point2, ...], closed: bool = False) -> Polyline:
    return Polyline(tuple(Vec2.from_xy(point) for point in points), closed=closed)


def spline(points: list[Point2] | tuple[Point2, ...]) -> Spline:
    return Spline(tuple(Vec2.from_xy(point) for point in points))


def sphere(centre: Point3, radius: float) -> Sphere:
    return Sphere(Vec3.from_xyz(centre), radius)


def prism(origin: Point3, size: Point3) -> Prism:
    return Prism(Vec3.from_xyz(origin), Vec3.from_xyz(size))
