from __future__ import annotations

from typing import TypeAlias

from cady.domain.base import Shape2D, Shape3D, axis_vector
from cady.domain.shapes2d import Arc, Circle, Line, Path, Polyline, Rectangle, Spline
from cady.domain.shapes3d import Extrusion, Prism, Revolution, Sphere
from cady.domain.vec import Vec2, Vec3
from cady.ops.curves2d import Point2, arc_points, circle_points, cubic_bezier_points
from cady.ops.meshes3d import (
    Point3,
)
from cady.ops.meshes3d import (
    extrusion_triangles as _primitive_extrusion_triangles,
)
from cady.ops.meshes3d import (
    prism_triangles as _primitive_prism_triangles,
)
from cady.ops.meshes3d import (
    revolution_triangles as _primitive_revolution_triangles,
)
from cady.ops.meshes3d import (
    sphere_triangles as _primitive_sphere_triangles,
)
from cady.ops.polygons2d import dedupe_closed, triangulate_polygon

Triangle2: TypeAlias = tuple[Vec2, Vec2, Vec2]
Triangle3: TypeAlias = tuple[Vec3, Vec3, Vec3]


def curves_to_polyline(shape: Shape2D, *, tolerance: float) -> Polyline:
    if tolerance <= 0:
        raise ValueError("tolerance must be positive")
    if isinstance(shape, Polyline):
        return shape
    if isinstance(shape, Rectangle):
        loops = tuple(curves_to_polyline(h, tolerance=tolerance) for h in shape.inner_loops)
        return Polyline(shape.corners(), closed=True, inner_loops=loops)
    if isinstance(shape, Line):
        return Polyline((shape.a, shape.b), closed=False)
    if isinstance(shape, Circle):
        circle_vertices = _vec2s(
            circle_points(shape.centre.tuple(), shape.radius, tolerance=tolerance)
        )
        loops = tuple(curves_to_polyline(h, tolerance=tolerance) for h in shape.inner_loops)
        return Polyline(circle_vertices, closed=True, inner_loops=loops)
    if isinstance(shape, Arc):
        return Polyline(
            _vec2s(
                arc_points(
                    shape.centre.tuple(),
                    shape.radius,
                    shape.start_rad,
                    shape.end_rad,
                    tolerance=tolerance,
                )
            ),
            closed=False,
        )
    if isinstance(shape, Spline):
        spline_vertices = _vec2s(
            cubic_bezier_points(
                tuple(point.tuple() for point in shape.control_points),
                tolerance=tolerance,
            )
        )
        loops = tuple(curves_to_polyline(h, tolerance=tolerance) for h in shape.inner_loops)
        return Polyline(spline_vertices, closed=shape.closed, inner_loops=loops)
    if isinstance(shape, Path):
        pts: list[Vec2] = []
        for segment in shape.segments:
            flattened = curves_to_polyline(segment, tolerance=tolerance).points()
            if pts:
                pts.extend(flattened[1:])
            else:
                pts.extend(flattened)
        if shape.closed and pts[0] == pts[-1]:
            pts.pop()
        loops = tuple(curves_to_polyline(h, tolerance=tolerance) for h in shape.inner_loops)
        return Polyline(tuple(pts), closed=shape.closed, inner_loops=loops)
    raise TypeError(f"unsupported Shape2D {type(shape).__name__}")


def polygon_to_triangles(shape: Shape2D, *, tolerance: float) -> list[Triangle2]:
    if not shape.closed:
        raise ValueError("polygon_to_triangles requires a closed Shape2D")
    flattened = curves_to_polyline(shape, tolerance=tolerance)
    outer = _points2(flattened.points())
    holes = tuple(
        _points2(curves_to_polyline(hole, tolerance=tolerance).points())
        for hole in flattened.inner_loops
    )
    return [
        _triangle2(triangle)
        for triangle in triangulate_polygon(outer, holes, tolerance=tolerance)
    ]


def prism_to_triangles(shape: Prism) -> list[Triangle3]:
    return [
        _triangle3(triangle)
        for triangle in _primitive_prism_triangles(shape.origin.tuple(), shape.size.tuple())
    ]


def extrusion_to_triangles(extrusion: Extrusion, *, tolerance: float) -> list[Triangle3]:
    flattened = curves_to_polyline(extrusion.profile, tolerance=tolerance)
    outer = _points2(flattened.points())
    holes = tuple(
        _points2(curves_to_polyline(hole, tolerance=tolerance).points())
        for hole in flattened.inner_loops
    )
    cap2 = triangulate_polygon(outer, holes, tolerance=tolerance)
    loops = (outer, *holes)
    hole_flags = (False, *(True for _hole in holes))
    axis = axis_vector(extrusion.axis)
    axis_name = extrusion.axis if isinstance(extrusion.axis, str) else None
    return [
        _triangle3(triangle)
        for triangle in _primitive_extrusion_triangles(
            cap2,
            loops,
            hole_flags,
            offset=extrusion.offset.tuple(),
            axis=axis.tuple(),
            axis_name=axis_name,
            distance=extrusion.distance,
        )
    ]


def revolution_to_triangles(revolution: Revolution, *, tolerance: float) -> list[Triangle3]:
    profile = curves_to_polyline(revolution.profile, tolerance=tolerance)
    return [
        _triangle3(triangle)
        for triangle in _primitive_revolution_triangles(
            _points2(profile.points()),
            axis_origin=revolution.axis_origin.tuple(),
            axis_direction=revolution.axis_direction.tuple(),
            angle_rad=revolution.angle_rad,
            tolerance=tolerance,
        )
    ]


def sphere_to_triangles(sphere: Sphere, *, tolerance: float) -> list[Triangle3]:
    return [
        _triangle3(triangle)
        for triangle in _primitive_sphere_triangles(
            sphere.centre.tuple(),
            sphere.radius,
            tolerance=tolerance,
        )
    ]


def triangles_for_solid(shape: Shape3D, *, tolerance: float) -> list[Triangle3]:
    if isinstance(shape, Prism):
        return prism_to_triangles(shape)
    if isinstance(shape, Extrusion):
        return extrusion_to_triangles(shape, tolerance=tolerance)
    if isinstance(shape, Revolution):
        return revolution_to_triangles(shape, tolerance=tolerance)
    if isinstance(shape, Sphere):
        return sphere_to_triangles(shape, tolerance=tolerance)
    raise TypeError(f"unsupported Shape3D {type(shape).__name__}")


def normal_for_triangle(triangle: Triangle3) -> Vec3:
    return _normal(*triangle)


def _vec2s(points: tuple[Point2, ...]) -> tuple[Vec2, ...]:
    return tuple(Vec2(x, y) for x, y in points)


def _points2(points: tuple[Vec2, ...]) -> tuple[Point2, ...]:
    return dedupe_closed(tuple(point.tuple() for point in points))


def _triangle2(triangle: tuple[Point2, Point2, Point2]) -> Triangle2:
    return tuple(Vec2(x, y) for x, y in triangle)  # type: ignore[return-value]


def _triangle3(triangle: tuple[Point3, Point3, Point3]) -> Triangle3:
    return tuple(Vec3(x, y, z) for x, y, z in triangle)  # type: ignore[return-value]


def _normal(a: Vec3, b: Vec3, c: Vec3) -> Vec3:
    n = (b - a).cross(c - a)
    try:
        return n.normalised()
    except ValueError:
        return Vec3(0, 0, 0)
