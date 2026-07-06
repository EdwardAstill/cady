"""Primitive mesh and triangle construction helpers."""

from __future__ import annotations

from math import acos, ceil, cos, pi, sin
from typing import TYPE_CHECKING, TypeAlias

from cady.operations.mesh.construction import dedupe_closed, mesh_from_triangles
from cady.operations.primitives import add3, scale3
from cady.utils import positive, positive_tolerance

if TYPE_CHECKING:
    from cady.geometry.mesh import Mesh3
    from cady.geometry.plane3 import Plane3

Point2: TypeAlias = tuple[float, float]
Point3Tuple: TypeAlias = tuple[float, float, float]
Point3: TypeAlias = tuple[float, float, float]
Triangle3: TypeAlias = tuple[Point3Tuple, Point3Tuple, Point3Tuple]
Triangle2: TypeAlias = tuple[Point2, Point2, Point2]


def segments_for_circle(radius: float, tolerance: float) -> int:
    """Estimate a polygon segment count that stays within a chord error."""
    tolerance = max(float(tolerance), 1e-9)
    if tolerance >= radius:
        return 12
    angle = 2.0 * acos(max(-1.0, min(1.0, 1.0 - tolerance / radius)))
    return max(12, ceil((2.0 * pi) / angle))


def prism_triangles(origin: Point3Tuple, size: Point3Tuple) -> list[Triangle3]:
    """Return triangles for an axis-aligned prism."""
    x0, y0, z0 = origin
    x1, y1, z1 = x0 + size[0], y0 + size[1], z0 + size[2]
    p = (
        (x0, y0, z0),
        (x1, y0, z0),
        (x1, y1, z0),
        (x0, y1, z0),
        (x0, y0, z1),
        (x1, y0, z1),
        (x1, y1, z1),
        (x0, y1, z1),
    )
    faces = (
        (0, 2, 1, 0, 3, 2),
        (4, 5, 6, 4, 6, 7),
        (0, 1, 5, 0, 5, 4),
        (1, 2, 6, 1, 6, 5),
        (2, 3, 7, 2, 7, 6),
        (3, 0, 4, 3, 4, 7),
    )
    return [(p[a], p[b], p[c]) for face in faces for a, b, c in (face[:3], face[3:])]


def basis_for_axis(
    axis: Point3Tuple,
    axis_name: str | None = None,
) -> tuple[Point3Tuple, Point3Tuple, Point3Tuple]:
    """Build a local orthonormal basis whose ``w`` axis follows ``axis``."""
    w = _normalised(axis)
    u = (1.0, 0.0, 0.0) if abs(w[2]) == 1 else _normalised(_cross((0.0, 0.0, 1.0), w))
    v = _normalised(_cross(w, u))
    if axis_name in {"+y", "-y"}:
        u, v = (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)
    elif axis_name in {"+x", "-x"}:
        u, v = (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
    return u, v, w


def extrusion_triangles(
    cap_triangles: list[Triangle2],
    loops: tuple[tuple[Point2, ...], ...],
    hole_flags: tuple[bool, ...],
    *,
    offset: Point3Tuple,
    axis: Point3Tuple,
    axis_name: str | None,
    distance: float,
) -> list[Triangle3]:
    """Extrude triangulated caps and region side walls along an axis."""
    u, v, w = basis_for_axis(axis, axis_name)
    start = offset
    end = _add(offset, _scale(w, distance))
    tris: list[Triangle3] = []
    for a, b, c in cap_triangles:
        tris.append((_map2(c, start, u, v), _map2(b, start, u, v), _map2(a, start, u, v)))
        tris.append((_map2(a, end, u, v), _map2(b, end, u, v), _map2(c, end, u, v)))
    for loop, is_hole in zip(loops, hole_flags, strict=True):
        pts = dedupe_closed(loop)
        for a, b in zip(pts, pts[1:] + pts[:1], strict=True):
            a0, b0 = _map2(a, start, u, v), _map2(b, start, u, v)
            a1, b1 = _map2(a, end, u, v), _map2(b, end, u, v)
            if is_hole:
                tris.append((a0, b1, b0))
                tris.append((a0, a1, b1))
            else:
                tris.append((a0, b0, b1))
                tris.append((a0, b1, a1))
    return tris


def revolution_triangles(
    profile_points: tuple[Point2, ...],
    *,
    axis_origin: Point3Tuple,
    axis_direction: Point3Tuple,
    angle_rad: float,
    tolerance: float,
) -> list[Triangle3]:
    """Approximate a surface of revolution around the positive Z axis."""
    pts2 = dedupe_closed(profile_points)
    axis = _normalised(axis_direction)
    if axis != (0.0, 0.0, 1.0):
        raise ValueError("Stage 1 revolution tessellation supports +Z axis")
    radius = max(abs(p[0] - axis_origin[0]) for p in pts2) or 1.0
    steps = max(12, ceil(abs(angle_rad) * radius / max(tolerance * 8, 1e-6)))
    steps = min(steps, 160)
    rings: list[list[Point3]] = []
    for i in range(steps):
        angle = angle_rad * i / steps
        ca, sa = cos(angle), sin(angle)
        rings.append([(p[0] * ca, p[0] * sa, p[1]) for p in pts2])
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


def sphere_triangles(centre: Point3Tuple, radius: float, *, tolerance: float) -> list[Triangle3]:
    """Approximate a sphere with latitude-longitude triangles."""
    rings = min(64, max(8, segments_for_circle(radius, tolerance) // 2))
    segs = rings * 2
    tris: list[Triangle3] = []
    for i in range(rings):
        theta0 = pi * i / rings
        theta1 = pi * (i + 1) / rings
        for j in range(segs):
            phi0 = 2 * pi * j / segs
            phi1 = 2 * pi * (j + 1) / segs
            pts: list[Point3] = []
            for theta, phi in ((theta0, phi0), (theta1, phi0), (theta1, phi1), (theta0, phi1)):
                pts.append(
                    _add(
                        centre,
                        (
                            radius * sin(theta) * cos(phi),
                            radius * sin(theta) * sin(phi),
                            radius * cos(theta),
                        ),
                    )
                )
            if pts[0] != pts[1] and pts[1] != pts[2]:
                tris.append((pts[0], pts[1], pts[2]))
            if pts[0] != pts[2] and pts[2] != pts[3]:
                tris.append((pts[0], pts[2], pts[3]))
    return tris


def validate_tolerance(tolerance: float) -> float:
    return positive_tolerance(tolerance)


def validate_positive(value: float, name: str) -> float:
    return positive(value, name)


def box_mesh(plane: Plane3, *, width: float, depth: float, height: float) -> Mesh3:
    from cady.geometry.mesh import Mesh3

    width = validate_positive(width, "width")
    depth = validate_positive(depth, "depth")
    height = validate_positive(height, "height")
    z = scale3(plane.normal, height)
    vertices = (
        plane.point(0.0, 0.0),
        plane.point(width, 0.0),
        plane.point(width, depth),
        plane.point(0.0, depth),
        add3(plane.point(0.0, 0.0), z),
        add3(plane.point(width, 0.0), z),
        add3(plane.point(width, depth), z),
        add3(plane.point(0.0, depth), z),
    )
    faces = (
        (0, 2, 1),
        (0, 3, 2),
        (4, 5, 6),
        (4, 6, 7),
        (0, 1, 5),
        (0, 5, 4),
        (1, 2, 6),
        (1, 6, 5),
        (2, 3, 7),
        (2, 7, 6),
        (3, 0, 4),
        (3, 4, 7),
    )
    return Mesh3(vertices, faces)


def cylinder_mesh(
    plane: Plane3,
    *,
    radius: float,
    height: float,
    tolerance: float,
) -> Mesh3:
    from cady.geometry.mesh import Mesh3

    radius = validate_positive(radius, "radius")
    height = validate_positive(height, "height")
    tolerance = validate_tolerance(tolerance)
    segments = segments_for_circle(radius, tolerance)
    top_offset = scale3(plane.normal, height)
    bottom = tuple(
        plane.point(
            radius * cos(2.0 * pi * index / segments),
            radius * sin(2.0 * pi * index / segments),
        )
        for index in range(segments)
    )
    top = tuple(add3(vertex, top_offset) for vertex in bottom)
    bottom_centre = plane.origin
    top_centre = add3(plane.origin, top_offset)
    vertices = bottom + top + (bottom_centre, top_centre)
    bottom_index = segments * 2
    top_index = bottom_index + 1
    faces: list[tuple[int, int, int]] = []
    for index in range(segments):
        next_index = (index + 1) % segments
        faces.append((bottom_index, next_index, index))
        faces.append((top_index, segments + index, segments + next_index))
        faces.append((index, next_index, segments + next_index))
        faces.append((index, segments + next_index, segments + index))
    return Mesh3(vertices, tuple(faces))


def sphere_mesh(plane: Plane3, *, radius: float, tolerance: float) -> Mesh3:
    radius = validate_positive(radius, "radius")
    tolerance = validate_tolerance(tolerance)
    triangles = tuple(
        tuple((float(point[0]), float(point[1]), float(point[2])) for point in triangle)
        for triangle in sphere_triangles(plane.origin, radius, tolerance=tolerance)
    )
    return mesh_from_triangles(triangles)  # type: ignore[arg-type]


def _map2(point: Point2, origin: Point3Tuple, u: Point3Tuple, v: Point3Tuple) -> Point3Tuple:
    return _add(origin, _add(_scale(u, point[0]), _scale(v, point[1])))


def _add(a: Point3Tuple, b: Point3Tuple) -> Point3Tuple:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a: Point3Tuple, scale: float) -> Point3Tuple:
    return (a[0] * scale, a[1] * scale, a[2] * scale)


def _dot(a: Point3Tuple, b: Point3Tuple) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Point3Tuple, b: Point3Tuple) -> Point3Tuple:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _normalised(a: Point3Tuple) -> Point3Tuple:
    length = _dot(a, a) ** 0.5
    if length == 0:
        raise ValueError("zero-length vector")
    return (a[0] / length, a[1] / length, a[2] / length)


__all__ = [
    "basis_for_axis",
    "box_mesh",
    "cylinder_mesh",
    "extrusion_triangles",
    "prism_triangles",
    "revolution_triangles",
    "segments_for_circle",
    "sphere_mesh",
    "sphere_triangles",
    "validate_positive",
    "validate_tolerance",
]
