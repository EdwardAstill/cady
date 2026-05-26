from __future__ import annotations

from math import acos, ceil, cos, pi, sin, sqrt
from typing import TypeAlias

from cady.errors import WriteError
from cady.geom.base import AxisString, Shape2D, Shape3D, axis_vector
from cady.geom.shapes2d import Arc, Circle, Line, Path, Polyline, Rectangle, Spline
from cady.geom.shapes3d import Extrusion, Prism, Revolution, Sphere
from cady.geom.vec import Vec2, Vec3

Triangle2: TypeAlias = tuple[Vec2, Vec2, Vec2]
Triangle3: TypeAlias = tuple[Vec3, Vec3, Vec3]


def _segments_for_circle(radius: float, tolerance: float) -> int:
    tolerance = max(float(tolerance), 1e-9)
    if tolerance >= radius:
        return 12
    angle = 2 * acos(max(-1.0, min(1.0, 1 - tolerance / radius)))
    return max(12, ceil((2 * pi) / angle))


def _dedupe_closed(points: list[Vec2]) -> tuple[Vec2, ...]:
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
    return tuple(points)


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
        n = _segments_for_circle(shape.radius, tolerance)
        pts = [
            Vec2(
                shape.centre.x + shape.radius * cos(2 * pi * i / n),
                shape.centre.y + shape.radius * sin(2 * pi * i / n),
            )
            for i in range(n)
        ]
        loops = tuple(curves_to_polyline(h, tolerance=tolerance) for h in shape.inner_loops)
        return Polyline(tuple(pts), closed=True, inner_loops=loops)
    if isinstance(shape, Arc):
        sweep = shape.end_rad - shape.start_rad
        n = max(2, ceil(abs(sweep) / (2 * pi) * _segments_for_circle(shape.radius, tolerance)))
        pts = [
            Vec2(
                shape.centre.x + shape.radius * cos(shape.start_rad + sweep * i / n),
                shape.centre.y + shape.radius * sin(shape.start_rad + sweep * i / n),
            )
            for i in range(n + 1)
        ]
        return Polyline(tuple(pts), closed=False)
    if isinstance(shape, Spline):
        pts: list[Vec2] = []
        samples = max(8, ceil(1 / sqrt(tolerance)))
        cps = shape.control_points
        for start in range(0, len(cps) - 1, 3):
            p0, p1, p2, p3 = cps[start : start + 4]
            for i in range(samples + 1):
                if pts and i == 0:
                    continue
                t = i / samples
                u = 1 - t
                pts.append(p0 * (u**3) + p1 * (3 * u * u * t) + p2 * (3 * u * t * t) + p3 * (t**3))
        loops = tuple(curves_to_polyline(h, tolerance=tolerance) for h in shape.inner_loops)
        return Polyline(tuple(pts), closed=shape.closed, inner_loops=loops)
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


def _area2(points: tuple[Vec2, ...]) -> float:
    return (
        sum(a.x * b.y - b.x * a.y for a, b in zip(points, points[1:] + points[:1], strict=True)) / 2
    )


def _point_in_poly(point: Vec2, poly: tuple[Vec2, ...]) -> bool:
    inside = False
    j = len(poly) - 1
    for i, pi_ in enumerate(poly):
        pj = poly[j]
        if ((pi_.y > point.y) != (pj.y > point.y)) and (
            point.x < (pj.x - pi_.x) * (point.y - pi_.y) / (pj.y - pi_.y) + pi_.x
        ):
            inside = not inside
        j = i
    return inside


def _fan(points: tuple[Vec2, ...]) -> list[Triangle2]:
    if _area2(points) < 0:
        points = tuple(reversed(points))
    return [(points[0], points[i], points[i + 1]) for i in range(1, len(points) - 1)]


def _is_self_intersecting(points: tuple[Vec2, ...]) -> bool:
    def ccw(a: Vec2, b: Vec2, c: Vec2) -> bool:
        return (c.y - a.y) * (b.x - a.x) > (b.y - a.y) * (c.x - a.x)

    edges = list(zip(points, points[1:] + points[:1], strict=True))
    for i, (a, b) in enumerate(edges):
        for j, (c, d) in enumerate(edges):
            if abs(i - j) <= 1 or {i, j} == {0, len(edges) - 1}:
                continue
            if ccw(a, c, d) != ccw(b, c, d) and ccw(a, b, c) != ccw(a, b, d):
                return True
    return False


def polygon_to_triangles(shape: Shape2D, *, tolerance: float) -> list[Triangle2]:
    if not shape.closed:
        raise ValueError("polygon_to_triangles requires a closed Shape2D")
    flattened = curves_to_polyline(shape, tolerance=tolerance)
    outer = _dedupe_closed(list(flattened.points()))
    if _is_self_intersecting(outer):
        preview = ", ".join(str(p.tuple()) for p in outer[:3])
        raise WriteError(f"self-intersecting profile near first 3 points: {preview}")
    holes = [
        _dedupe_closed(list(curves_to_polyline(h, tolerance=tolerance).points()))
        for h in flattened.inner_loops
    ]
    if not holes:
        return _fan(outer)

    mn, mx = flattened.bounds()
    span = max(mx.x - mn.x, mx.y - mn.y)
    grid = min(160, max(48, ceil(span / max(tolerance * 8, span / 96))))
    dx = (mx.x - mn.x) / grid
    dy = (mx.y - mn.y) / grid
    tris: list[Triangle2] = []

    def allowed(point: Vec2) -> bool:
        return _point_in_poly(point, outer) and not any(
            _point_in_poly(point, hole) for hole in holes
        )

    for ix in range(grid):
        for iy in range(grid):
            p00 = Vec2(mn.x + ix * dx, mn.y + iy * dy)
            p10 = Vec2(p00.x + dx, p00.y)
            p11 = Vec2(p00.x + dx, p00.y + dy)
            p01 = Vec2(p00.x, p00.y + dy)
            centre = Vec2(p00.x + dx / 2, p00.y + dy / 2)
            corners = (p00, p10, p11, p01)
            if allowed(centre) and all(allowed(p) for p in corners):
                tris.append((p00, p10, p11))
                tris.append((p00, p11, p01))
    return tris


def _normal(a: Vec3, b: Vec3, c: Vec3) -> Vec3:
    n = (b - a).cross(c - a)
    try:
        return n.normalised()
    except ValueError:
        return Vec3(0, 0, 0)


def prism_to_triangles(shape: Prism) -> list[Triangle3]:
    p = shape.corners()
    faces = (
        (0, 2, 1, 0, 3, 2),
        (4, 5, 6, 4, 6, 7),
        (0, 1, 5, 0, 5, 4),
        (1, 2, 6, 1, 6, 5),
        (2, 3, 7, 2, 7, 6),
        (3, 0, 4, 3, 4, 7),
    )
    return [(p[a], p[b], p[c]) for face in faces for a, b, c in (face[:3], face[3:])]


def _basis_for_axis(axis: AxisString | Vec3) -> tuple[Vec3, Vec3, Vec3]:
    w = axis_vector(axis)
    u = Vec3(1, 0, 0) if abs(w.z) == 1 else Vec3(0, 0, 1).cross(w).normalised()
    v = w.cross(u).normalised()
    if axis in {"+y", "-y"}:
        u, v = Vec3(1, 0, 0), Vec3(0, 0, 1)
    elif axis in {"+x", "-x"}:
        u, v = Vec3(0, 1, 0), Vec3(0, 0, 1)
    return u, v, w


def _map2(point: Vec2, origin: Vec3, u: Vec3, v: Vec3) -> Vec3:
    return origin + u * point.x + v * point.y


def extrusion_to_triangles(extrusion: Extrusion, *, tolerance: float) -> list[Triangle3]:
    cap2 = polygon_to_triangles(extrusion.profile, tolerance=tolerance)
    u, v, w = _basis_for_axis(extrusion.axis)
    start = extrusion.offset
    end = extrusion.offset + w * extrusion.distance
    tris: list[Triangle3] = []
    for a, b, c in cap2:
        tris.append((_map2(c, start, u, v), _map2(b, start, u, v), _map2(a, start, u, v)))
        tris.append((_map2(a, end, u, v), _map2(b, end, u, v), _map2(c, end, u, v)))
    loops = [curves_to_polyline(extrusion.profile, tolerance=tolerance).points()]
    loops.extend(
        curves_to_polyline(h, tolerance=tolerance).points() for h in extrusion.profile.inner_loops
    )
    for loop in loops:
        pts = _dedupe_closed(list(loop))
        for a, b in zip(pts, pts[1:] + pts[:1], strict=True):
            a0, b0 = _map2(a, start, u, v), _map2(b, start, u, v)
            a1, b1 = _map2(a, end, u, v), _map2(b, end, u, v)
            tris.append((a0, b0, b1))
            tris.append((a0, b1, a1))
    return tris


def revolution_to_triangles(revolution: Revolution, *, tolerance: float) -> list[Triangle3]:
    profile = curves_to_polyline(revolution.profile, tolerance=tolerance)
    pts2 = _dedupe_closed(list(profile.points()))
    axis = revolution.axis_direction.normalised()
    if axis != Vec3(0, 0, 1):
        raise ValueError("Stage 1 revolution tessellation supports +Z axis")
    radius = max(abs(p.x - revolution.axis_origin.x) for p in pts2) or 1.0
    steps = max(12, ceil(abs(revolution.angle_rad) * radius / max(tolerance * 8, 1e-6)))
    steps = min(steps, 160)
    rings: list[list[Vec3]] = []
    for i in range(steps):
        angle = revolution.angle_rad * i / steps
        ca, sa = cos(angle), sin(angle)
        rings.append([Vec3(p.x * ca, p.x * sa, p.y) for p in pts2])
    tris: list[Triangle3] = []
    for i in range(steps):
        nxt = (i + 1) % steps
        for j in range(len(pts2)):
            a = rings[i][j]
            b = rings[i][(j + 1) % len(pts2)]
            c = rings[nxt][(j + 1) % len(pts2)]
            d = rings[nxt][j]
            tris.append((a, b, c))
            tris.append((a, c, d))
    return tris


def sphere_to_triangles(sphere: Sphere, *, tolerance: float) -> list[Triangle3]:
    rings = min(64, max(8, _segments_for_circle(sphere.radius, tolerance) // 2))
    segs = rings * 2
    tris: list[Triangle3] = []
    for i in range(rings):
        theta0 = pi * i / rings
        theta1 = pi * (i + 1) / rings
        for j in range(segs):
            phi0 = 2 * pi * j / segs
            phi1 = 2 * pi * (j + 1) / segs
            pts: list[Vec3] = []
            for theta, phi in ((theta0, phi0), (theta1, phi0), (theta1, phi1), (theta0, phi1)):
                pts.append(
                    sphere.centre
                    + Vec3(
                        sphere.radius * sin(theta) * cos(phi),
                        sphere.radius * sin(theta) * sin(phi),
                        sphere.radius * cos(theta),
                    )
                )
            if pts[0] != pts[1] and pts[1] != pts[2]:
                tris.append((pts[0], pts[1], pts[2]))
            if pts[0] != pts[2] and pts[2] != pts[3]:
                tris.append((pts[0], pts[2], pts[3]))
    return tris


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
