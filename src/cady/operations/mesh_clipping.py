"""Plane clipping for triangle meshes with optional planar caps."""

from __future__ import annotations

from typing import Literal

import numpy as np
from numpy.typing import NDArray

from cady.operations._mesh_arrays import coerce_mesh, return_mesh
from cady.operations.arrays3 import ArrayMesh3
from cady.operations.mesh_boundaries import Segment
from cady.operations.mesh_caps import cap_loops_to_faces
from cady.operations.planes import Point3Array, unit3, vector3

KeepSide = Literal["positive", "negative"]
Face = tuple[int, int, int]


def cut_mesh_by_plane(
    mesh_or_vertices: ArrayMesh3 | object,
    faces: object | None = None,
    plane_origin: object | None = None,
    plane_normal: object | None = None,
    *,
    keep: KeepSide = "positive",
    cap: bool = True,
    tolerance: float = 1e-9,
) -> ArrayMesh3 | tuple[NDArray[np.float64], NDArray[np.int64], NDArray[np.int64]]:
    """Return the part of a triangle mesh on one side of a plane.

    The positive side is where ``dot(point - plane_origin, plane_normal) >= 0``.
    Set ``keep="negative"`` to retain the opposite half-space. When ``cap`` is
    true, the cut boundary is filled for simple non-nested loops.
    """
    if keep not in {"positive", "negative"}:
        raise ValueError("keep must be 'positive' or 'negative'")
    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive")
    if plane_origin is None or plane_normal is None:
        raise TypeError("plane_origin and plane_normal are required")

    mesh, as_tuple = coerce_mesh(mesh_or_vertices, faces)
    origin = vector3(plane_origin, name="plane_origin")
    normal = unit3(plane_normal, name="plane_normal")
    if keep == "negative":
        normal = -normal

    output_vertices: list[Point3Array] = []
    output_faces: list[Face] = []
    index_by_key: dict[tuple[int, int, int], int] = {}
    cap_segments: list[Segment] = []

    source_triangles = np.asarray(mesh.vertices, dtype=np.float64)[
        np.asarray(mesh.faces, dtype=np.int64)
    ]
    for triangle in source_triangles:
        points = [triangle[index] for index in range(3)]
        distances = [float(np.dot(point - origin, normal)) for point in points]
        clipped_polygon = _clip_triangle(points, distances, tolerance)

        if len(clipped_polygon) >= 3:
            polygon_indices = [
                _add_vertex(point, output_vertices, index_by_key, tolerance)
                for point in clipped_polygon
            ]
            first = clipped_polygon[0]
            first_index = polygon_indices[0]
            for index in range(1, len(clipped_polygon) - 1):
                second = clipped_polygon[index]
                third = clipped_polygon[index + 1]
                if not _is_degenerate_triangle(first, second, third, tolerance):
                    output_faces.append(
                        (first_index, polygon_indices[index], polygon_indices[index + 1])
                    )

        if cap and any(distance < -tolerance for distance in distances):
            # Collect the cut segment for this source triangle; later passes stitch loops.
            cut_points = _plane_points(clipped_polygon, origin, normal, tolerance)
            if len(cut_points) == 2:
                start = _add_vertex(cut_points[0], output_vertices, index_by_key, tolerance)
                end = _add_vertex(cut_points[1], output_vertices, index_by_key, tolerance)
                if start != end:
                    cap_segments.append((start, end))

    if cap:
        output_faces.extend(
            cap_loops_to_faces(output_vertices, cap_segments, origin, normal, tolerance=tolerance)
        )

    if not output_vertices or not output_faces:
        return return_mesh(
            ArrayMesh3(
                np.empty((0, 3), dtype=np.float64),
                np.empty((0, 3), dtype=np.int64),
                np.empty((0, 2), dtype=np.int64),
            ),
            as_tuple,
        )

    return return_mesh(
        ArrayMesh3(
            np.array(output_vertices, dtype=np.float64),
            np.array(output_faces, dtype=np.int64),
            np.empty((0, 2), dtype=np.int64),
        ),
        as_tuple,
    )


def _point_key(point: Point3Array, tolerance: float) -> tuple[int, int, int]:
    return (
        int(round(float(point[0]) / tolerance)),
        int(round(float(point[1]) / tolerance)),
        int(round(float(point[2]) / tolerance)),
    )


def _add_vertex(
    point: Point3Array,
    vertices: list[Point3Array],
    index_by_key: dict[tuple[int, int, int], int],
    tolerance: float,
) -> int:
    key = _point_key(point, tolerance)
    existing = index_by_key.get(key)
    if existing is not None:
        return existing
    index = len(vertices)
    vertices.append(np.array(point, dtype=np.float64, copy=True))
    index_by_key[key] = index
    return index


def _intersect_edge(
    start: Point3Array,
    end: Point3Array,
    start_distance: float,
    end_distance: float,
) -> Point3Array:
    denominator = start_distance - end_distance
    if denominator == 0.0:
        return np.array(start, dtype=np.float64, copy=True)
    fraction = max(0.0, min(1.0, start_distance / denominator))
    return start + (end - start) * fraction


def _clip_triangle(
    points: list[Point3Array],
    distances: list[float],
    tolerance: float,
) -> list[Point3Array]:
    """Clip one triangle against the kept half-space of a plane."""
    clipped: list[Point3Array] = []
    for index, start in enumerate(points):
        end_index = (index + 1) % len(points)
        end = points[end_index]
        start_distance = distances[index]
        end_distance = distances[end_index]
        start_inside = start_distance >= -tolerance
        end_inside = end_distance >= -tolerance

        if start_inside and end_inside:
            clipped.append(end)
        elif start_inside and not end_inside:
            clipped.append(_intersect_edge(start, end, start_distance, end_distance))
        elif not start_inside and end_inside:
            clipped.append(_intersect_edge(start, end, start_distance, end_distance))
            clipped.append(end)
    return clipped


def _is_degenerate_triangle(
    a: Point3Array,
    b: Point3Array,
    c: Point3Array,
    tolerance: float,
) -> bool:
    area_vector = np.cross(b - a, c - a)
    return float(np.linalg.norm(area_vector)) <= tolerance * tolerance


def _plane_points(
    polygon: list[Point3Array],
    origin: Point3Array,
    normal: Point3Array,
    tolerance: float,
) -> list[Point3Array]:
    points: list[Point3Array] = []
    for point in polygon:
        distance = float(np.dot(point - origin, normal))
        if abs(distance) <= tolerance and not any(
            np.linalg.norm(point - existing) <= tolerance for existing in points
        ):
            points.append(point)
    return points
