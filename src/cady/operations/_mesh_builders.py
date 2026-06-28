"""Build semantic Mesh3 values from primitive and profile descriptions."""

from __future__ import annotations

from math import cos, pi, sin

import numpy as np

from cady.geometry.frame3 import Frame3
from cady.geometry.mesh3 import Mesh3
from cady.operations.arrays2 import ArrayPolygon2
from cady.operations.mesh_primitives import sphere_triangles
from cady.operations.polygons2 import dedupe_closed, triangulate_polygon
from cady.operations.sampling2 import segments_for_circle
from cady.utils import finite, positive, positive_tolerance
from cady.vec import Vec3

Point2 = tuple[float, float]
Triangle3 = tuple[Vec3, Vec3, Vec3]


def validate_tolerance(tolerance: float) -> float:
    return positive_tolerance(tolerance)


def validate_positive(value: float, name: str) -> float:
    return positive(value, name)


def box_mesh(frame: Frame3, *, width: float, depth: float, height: float) -> Mesh3:
    width = validate_positive(width, "width")
    depth = validate_positive(depth, "depth")
    height = validate_positive(height, "height")
    z = frame.normal * height
    vertices = (
        frame.point(0.0, 0.0),
        frame.point(width, 0.0),
        frame.point(width, depth),
        frame.point(0.0, depth),
        frame.point(0.0, 0.0) + z,
        frame.point(width, 0.0) + z,
        frame.point(width, depth) + z,
        frame.point(0.0, depth) + z,
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
    frame: Frame3,
    *,
    radius: float,
    height: float,
    tolerance: float,
) -> Mesh3:
    radius = validate_positive(radius, "radius")
    height = validate_positive(height, "height")
    tolerance = validate_tolerance(tolerance)
    segments = segments_for_circle(radius, tolerance)
    top_offset = frame.normal * height
    bottom = tuple(
        frame.point(
            radius * cos(2.0 * pi * index / segments),
            radius * sin(2.0 * pi * index / segments),
        )
        for index in range(segments)
    )
    top = tuple(vertex + top_offset for vertex in bottom)
    bottom_centre = frame.origin
    top_centre = frame.origin + top_offset
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


def sphere_mesh(frame: Frame3, *, radius: float, tolerance: float) -> Mesh3:
    radius = validate_positive(radius, "radius")
    tolerance = validate_tolerance(tolerance)
    triangles = tuple(
        tuple(Vec3(*point) for point in triangle)
        for triangle in sphere_triangles(frame.origin.tuple(), radius, tolerance=tolerance)
    )
    return mesh_from_triangles(triangles)  # type: ignore[arg-type]


def face_mesh(profile: object, frame: Frame3, *, tolerance: float) -> Mesh3:
    polygon = polygon_from_profile(profile, tolerance=tolerance)
    cap_triangles = triangulate_polygon(
        _points2(polygon.outer),
        tuple(_points2(hole) for hole in polygon.holes),
        tolerance=tolerance,
    )
    triangles = tuple(
        (frame.point(*a), frame.point(*b), frame.point(*c))
        for a, b, c in cap_triangles
    )
    return mesh_from_triangles(triangles)


def extrusion_mesh(
    profile: object,
    frame: Frame3,
    *,
    distance: float,
    tolerance: float,
) -> Mesh3:
    distance = finite(distance, "distance")
    if distance == 0.0:
        raise ValueError("distance must be finite and non-zero")
    polygon = polygon_from_profile(profile, tolerance=tolerance)
    cap_triangles = triangulate_polygon(
        _points2(polygon.outer),
        tuple(_points2(hole) for hole in polygon.holes),
        tolerance=tolerance,
    )
    end_origin = frame.origin + frame.normal * distance
    end_frame = Frame3(end_origin, frame.x_axis, frame.normal)
    triangles: list[Triangle3] = []
    for a, b, c in cap_triangles:
        triangles.append((frame.point(*c), frame.point(*b), frame.point(*a)))
        triangles.append((end_frame.point(*a), end_frame.point(*b), end_frame.point(*c)))
    for loop, is_hole in _loops_from_polygon(polygon):
        points = dedupe_closed(loop)
        for a, b in zip(points, points[1:] + points[:1], strict=True):
            a0 = frame.point(*a)
            b0 = frame.point(*b)
            a1 = end_frame.point(*a)
            b1 = end_frame.point(*b)
            if is_hole:
                triangles.append((a0, b1, b0))
                triangles.append((a0, a1, b1))
            else:
                triangles.append((a0, b0, b1))
                triangles.append((a0, b1, a1))
    return mesh_from_triangles(tuple(triangles))


def polygon_from_profile(profile: object, *, tolerance: float) -> ArrayPolygon2:
    tolerance = validate_tolerance(tolerance)
    to_array = getattr(profile, "to_array", None)
    if to_array is None:
        raise TypeError("profile must provide to_array(tolerance=...)")
    polygon = to_array(tolerance=tolerance)
    if not isinstance(polygon, ArrayPolygon2):
        outer = getattr(polygon, "outer", None)
        holes = getattr(polygon, "holes", ())
        if outer is None:
            raise TypeError(
                "profile.to_array(tolerance=...) must return an ArrayPolygon2-like object"
            )
        polygon = ArrayPolygon2(outer, tuple(holes))
    return polygon


def mesh_from_triangles(triangles: tuple[Triangle3, ...]) -> Mesh3:
    vertices: list[Vec3] = []
    faces: list[tuple[int, int, int]] = []
    for triangle in triangles:
        start = len(vertices)
        vertices.extend(triangle)
        faces.append((start, start + 1, start + 2))
    return Mesh3(tuple(vertices), tuple(faces))


def _points2(points: np.ndarray) -> tuple[Point2, ...]:
    return tuple((float(point[0]), float(point[1])) for point in points)


def _loops_from_polygon(polygon: ArrayPolygon2) -> tuple[tuple[tuple[Point2, ...], bool], ...]:
    outer = (_points2(polygon.outer), False)
    holes = tuple((_points2(hole), True) for hole in polygon.holes)
    return (outer, *holes)
