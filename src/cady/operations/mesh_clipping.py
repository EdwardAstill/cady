"""Clipping and planar closure helpers for existing triangle meshes."""

from __future__ import annotations

from typing import Literal, TypeAlias, TypeGuard, cast

import numpy as np
from numpy.typing import NDArray

from cady.errors import GeometryError
from cady.operations.mesh_topology import (
    boundary_edges,
    boundary_edges_from_faces,
    compact_mesh_data,
    prune_dangling_edges,
    stitch_segments,
)
from cady.operations.triangulation import triangulate2
from cady.utils import loop_edges

KeepSide = Literal["positive", "negative"]
Face: TypeAlias = tuple[int, int, int]
Segment: TypeAlias = tuple[int, int]
PointArray3 = NDArray[np.float64]
Point3Array = NDArray[np.float64]
FaceArray = NDArray[np.int64]
EdgeArray = NDArray[np.int64]
MeshArrays: TypeAlias = tuple[PointArray3, FaceArray, EdgeArray]


def coerce_mesh(
    mesh_or_vertices: object,
    faces: object | None,
    edges: object | None = None,
) -> MeshArrays:
    """Return coerced ``(vertices, faces, edges)`` arrays."""
    if faces is None and _is_mesh_arrays(mesh_or_vertices):
        vertices_value = mesh_or_vertices[0]
        faces_value = mesh_or_vertices[1]
        edges_value = mesh_or_vertices[2] if len(mesh_or_vertices) == 3 else None
        return coerce_mesh(vertices_value, faces_value, edges_value)

    if faces is None:
        raise TypeError("faces must be provided when passing vertices directly")
    vertices_np = _points3_array(mesh_or_vertices, name="vertices")
    faces_np = np.array(faces, dtype=np.int64, copy=True)
    edges_np = np.array(
        np.empty((0, 2), dtype=np.int64) if edges is None else edges,
        dtype=np.int64,
        copy=True,
    )
    if faces_np.size == 0:
        faces_np = np.empty((0, 3), dtype=np.int64)
    if edges_np.size == 0:
        edges_np = np.empty((0, 2), dtype=np.int64)
    return vertices_np, faces_np, edges_np


def close_planar_cap(
    mesh_or_vertices: object,
    faces: object | None = None,
    edges: object | None = None,
    plane_origin: object | None = None,
    plane_normal: object | None = None,
    *,
    tolerance: float = 1e-9,
    snap_tolerance: float | None = None,
) -> MeshArrays:
    """Cap an open mesh at an explicit plane."""
    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive")
    if snap_tolerance is not None and snap_tolerance <= 0.0:
        raise ValueError("snap_tolerance must be positive")
    if plane_origin is None or plane_normal is None:
        raise TypeError("plane_origin and plane_normal are required")
    mesh = coerce_mesh(mesh_or_vertices, faces, edges)
    vertices, mesh_faces, mesh_edges = mesh
    origin = _vector3(plane_origin, name="plane_origin")
    normal = _unit3(plane_normal, name="plane_normal")

    vertices_np = vertices.astype(np.float64, copy=False)
    if len(vertices_np) == 0:
        return mesh

    boundary = boundary_edges(mesh)
    if not boundary:
        return mesh

    vertices_list: list[Point3Array] = [
        np.array(vertex, dtype=np.float64, copy=True) for vertex in vertices_np
    ]

    projected_index: dict[int, int] = {}
    plane_segments: list[Segment] = []

    for a, b in boundary:
        dist_a = float(np.dot(vertices_np[a] - origin, normal))
        dist_b = float(np.dot(vertices_np[b] - origin, normal))
        on_a = abs(dist_a) <= tolerance
        on_b = abs(dist_b) <= tolerance

        if on_a and on_b:
            plane_segments.append((a, b))
        elif snap_tolerance is not None:
            near_a = not on_a and abs(dist_a) <= snap_tolerance
            near_b = not on_b and abs(dist_b) <= snap_tolerance
            if not near_a and not near_b:
                continue
            cap_a = _snapped_index(a, dist_a, on_a, origin, normal, vertices_list, projected_index)
            cap_b = _snapped_index(b, dist_b, on_b, origin, normal, vertices_list, projected_index)
            if cap_a is not None and cap_b is not None:
                plane_segments.append((cap_a, cap_b))

    if not plane_segments:
        return mesh

    cap_faces = _cap_loops_to_faces(
        vertices_list, plane_segments, origin, normal, tolerance=tolerance
    )
    if not cap_faces:
        return mesh

    out_vertices = vertices
    if projected_index:
        out_vertices = np.array(vertices_list, dtype=np.float64)

    all_faces = np.vstack([mesh_faces] + [np.array(cap_faces, dtype=np.int64)]).astype(
        np.int64, copy=False
    )
    return out_vertices, all_faces, mesh_edges


def close_boundary(
    mesh_or_vertices: object,
    faces: object | None = None,
    edges: object | None = None,
    *,
    tolerance: float = 1e-9,
) -> MeshArrays:
    """Close all planar boundary holes in a mesh."""
    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive")

    mesh = coerce_mesh(mesh_or_vertices, faces, edges)
    vertices, faces_array, mesh_edges = mesh
    boundary = boundary_edges(mesh)
    if not boundary:
        return mesh

    vertices_np = vertices.astype(np.float64, copy=False)
    loops = stitch_segments(boundary)
    if not loops:
        return mesh

    vertices_list: list[Point3Array] = [
        np.array(vertex, dtype=np.float64, copy=True) for vertex in vertices_np
    ]

    all_cap_faces: list[Face] = []
    for loop in loops:
        loop_points = vertices_np[loop]
        loop_origin, loop_normal = _fit_plane_svd(loop_points)
        deviation = _max_plane_deviation(loop_points, loop_origin, loop_normal)
        if deviation > tolerance:
            raise ValueError(
                f"Boundary loop is non-planar (max deviation {deviation:.3e} > "
                f"tolerance {tolerance:.3e}); "
                "close_holes is not implemented - use close_boundary for planar holes only"
            )
        projected = _project_loop(loop, vertices_list, loop_origin, loop_normal)
        all_cap_faces.extend(
            (loop[a], loop[c], loop[b]) for a, b, c in _triangulate_loop(projected, tolerance)
        )

    if not all_cap_faces:
        return mesh

    all_faces = np.vstack([faces_array] + [np.array(all_cap_faces, dtype=np.int64)]).astype(
        np.int64, copy=False
    )
    return vertices, all_faces, mesh_edges


def close_to_plane(
    mesh_or_vertices: object,
    faces: object | None = None,
    edges: object | None = None,
    plane_origin: object | None = None,
    plane_normal: object | None = None,
    *,
    tolerance: float = 1e-9,
    max_distance: float,
) -> MeshArrays:
    """Project near-plane mesh edges to a plane and create wall faces."""
    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive")
    if max_distance <= 0.0:
        raise ValueError("max_distance must be positive")
    if plane_origin is None or plane_normal is None:
        raise TypeError("plane_origin and plane_normal are required")

    mesh = coerce_mesh(mesh_or_vertices, faces, edges)
    vertices, mesh_faces, mesh_edges = mesh
    origin = _vector3(plane_origin, name="plane_origin")
    normal = _unit3(plane_normal, name="plane_normal")

    face_values = _faces_from_array(mesh_faces)
    source_edges = _edges_from_array(mesh_edges)
    has_display_edges = bool(source_edges)
    if not source_edges:
        source_edges = boundary_edges_from_faces(face_values)
    live_edges = prune_dangling_edges(source_edges)

    near_edges: list[Segment] = []
    for a, b in live_edges:
        dist_a = _signed_distance(vertices[a], origin, normal)
        dist_b = _signed_distance(vertices[b], origin, normal)
        if abs(dist_a) <= max_distance and abs(dist_b) <= max_distance:
            near_edges.append((a, b))

    if not near_edges:
        raise GeometryError("no edges found within max_distance of the plane")

    projected_index: dict[int, int] = {}
    all_vertices = _points_from_array(vertices)

    for a, b in near_edges:
        if a not in projected_index:
            projected_index[a] = len(all_vertices)
            all_vertices.append(_project_point(vertices[a], origin, normal))
        if b not in projected_index:
            projected_index[b] = len(all_vertices)
            all_vertices.append(_project_point(vertices[b], origin, normal))

    wall_faces: list[Face] = []
    for a, b in near_edges:
        pa = projected_index[a]
        pb = projected_index[b]
        wall_faces.append((a, b, pb))
        wall_faces.append((a, pb, pa))

    display_edges = live_edges if has_display_edges else ()
    compact_vertices, compact_faces, compact_edges = compact_mesh_data(
        all_vertices,
        face_values + tuple(wall_faces),
        display_edges,
    )
    return _mesh_arrays_from_topology(compact_vertices, compact_faces, compact_edges)


def cut_mesh_by_plane(
    mesh_or_vertices: object,
    faces: object | None = None,
    plane_origin: object | None = None,
    plane_normal: object | None = None,
    *,
    keep: KeepSide = "positive",
    cap: bool = True,
    tolerance: float = 1e-9,
) -> MeshArrays:
    """Return the part of a triangle mesh on one side of a plane."""
    if keep not in {"positive", "negative"}:
        raise ValueError("keep must be 'positive' or 'negative'")
    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive")
    if plane_origin is None or plane_normal is None:
        raise TypeError("plane_origin and plane_normal are required")

    mesh = coerce_mesh(mesh_or_vertices, faces)
    vertices, mesh_faces, _mesh_edges = mesh
    origin = _vector3(plane_origin, name="plane_origin")
    normal = _unit3(plane_normal, name="plane_normal")
    if keep == "negative":
        normal = -normal

    output_vertices: list[Point3Array] = []
    output_faces: list[Face] = []
    index_by_key: dict[tuple[int, int, int], int] = {}
    cap_segments: list[Segment] = []

    source_triangles = np.asarray(vertices, dtype=np.float64)[
        np.asarray(mesh_faces, dtype=np.int64)
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
            cut_points = _plane_points(clipped_polygon, origin, normal, tolerance)
            if len(cut_points) == 2:
                start = _add_vertex(cut_points[0], output_vertices, index_by_key, tolerance)
                end = _add_vertex(cut_points[1], output_vertices, index_by_key, tolerance)
                if start != end:
                    cap_segments.append((start, end))

    if cap:
        output_faces.extend(
            _cap_loops_to_faces(output_vertices, cap_segments, origin, normal, tolerance=tolerance)
        )

    if not output_vertices or not output_faces:
        return (
            np.empty((0, 3), dtype=np.float64),
            np.empty((0, 3), dtype=np.int64),
            np.empty((0, 2), dtype=np.int64),
        )

    return (
        np.array(output_vertices, dtype=np.float64),
        np.array(output_faces, dtype=np.int64),
        np.empty((0, 2), dtype=np.int64),
    )


def _is_mesh_arrays(
    value: object,
) -> TypeGuard[tuple[object, object] | tuple[object, object, object]]:
    if not isinstance(value, tuple):
        return False
    values = cast(tuple[object, ...], value)
    return len(values) in {2, 3}


def _float_array(value: object, *, name: str) -> NDArray[np.float64]:
    try:
        array = np.array(value, dtype=np.float64, copy=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    return array


def _points3_array(value: object, *, name: str) -> PointArray3:
    array = _float_array(value, name=name)
    if array.ndim != 2:
        raise ValueError(f"{name} must have rank 2")
    if array.shape[1] != 3:
        raise ValueError(f"{name} must have shape (n, 3)")
    return array


def _vector3(value: object, *, name: str) -> Point3Array:
    array = np.array(value, dtype=np.float64, copy=True)
    if array.shape != (3,) or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a finite 3D vector")
    return array


def _unit3(value: object, *, name: str) -> Point3Array:
    vector = _vector3(value, name=name)
    length = float(np.linalg.norm(vector))
    if length == 0.0:
        raise ValueError(f"{name} must be non-zero")
    return vector / length


def _points_from_array(vertices: PointArray3) -> list[tuple[float, float, float]]:
    return [(float(x), float(y), float(z)) for x, y, z in vertices]


def _faces_from_array(faces: FaceArray) -> tuple[Face, ...]:
    return tuple((int(a), int(b), int(c)) for a, b, c in faces)


def _edges_from_array(edges: EdgeArray) -> tuple[Segment, ...]:
    return tuple((int(a), int(b)) for a, b in edges)


def _mesh_arrays_from_topology(
    vertices: tuple[tuple[float, float, float], ...],
    faces: tuple[Face, ...],
    edges: tuple[Segment, ...],
) -> MeshArrays:
    vertices_array = np.array(vertices, dtype=np.float64)
    faces_array = np.array(faces, dtype=np.int64)
    edges_array = np.array(edges, dtype=np.int64)
    if vertices_array.size == 0:
        vertices_array = np.empty((0, 3), dtype=np.float64)
    if faces_array.size == 0:
        faces_array = np.empty((0, 3), dtype=np.int64)
    if edges_array.size == 0:
        edges_array = np.empty((0, 2), dtype=np.int64)
    return vertices_array, faces_array, edges_array


def _signed_distance(
    point: Point3Array,
    origin: Point3Array,
    normal: Point3Array,
) -> float:
    return float(np.dot(point - origin, normal))


def _project_point(
    point: Point3Array,
    origin: Point3Array,
    normal: Point3Array,
) -> tuple[float, float, float]:
    projected = point - normal * _signed_distance(point, origin, normal)
    return (float(projected[0]), float(projected[1]), float(projected[2]))


def _basis_for_plane(normal: Point3Array) -> tuple[Point3Array, Point3Array]:
    reference = (
        np.array([1.0, 0.0, 0.0], dtype=np.float64)
        if abs(float(normal[0])) < 0.9
        else np.array([0.0, 1.0, 0.0], dtype=np.float64)
    )
    u_axis = np.cross(normal, reference)
    u_axis = u_axis / np.linalg.norm(u_axis)
    v_axis = np.cross(normal, u_axis)
    return u_axis, v_axis


def _project_loop(
    loop: list[int],
    vertices: list[Point3Array],
    origin: Point3Array,
    normal: Point3Array,
) -> list[tuple[float, float]]:
    u_axis, v_axis = _basis_for_plane(normal)
    projected: list[tuple[float, float]] = []
    for vertex_index in loop:
        relative = vertices[vertex_index] - origin
        projected.append((float(np.dot(relative, u_axis)), float(np.dot(relative, v_axis))))
    return projected


def _fit_plane_svd(points: Point3Array) -> tuple[Point3Array, Point3Array]:
    centroid = points.mean(axis=0)
    centered = points - centroid
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    normal = vt[-1]
    if float(np.dot(normal, np.array([0.0, 0.0, 1.0]))) < 0.0:
        normal = -normal
    return centroid, normal


def _max_plane_deviation(
    points: Point3Array,
    origin: Point3Array,
    normal: Point3Array,
) -> float:
    return float(np.max(np.abs(np.dot(points - origin, normal))))


def _triangulate_loop(points: list[tuple[float, float]], tolerance: float) -> list[Face]:
    vertices = np.asarray(points, dtype=np.float64)
    edges = np.asarray(loop_edges(len(points)), dtype=np.int64)
    _vertices, faces = triangulate2(vertices, edges, tolerance=tolerance)
    return [(int(face[0]), int(face[1]), int(face[2])) for face in faces]


def _cap_loops_to_faces(
    vertices: list[Point3Array],
    cap_segments: list[Segment],
    plane_origin: Point3Array,
    plane_normal: Point3Array,
    *,
    tolerance: float,
) -> list[Face]:
    if not cap_segments:
        return []
    cap_loops = stitch_segments(cap_segments)
    projected_loops = [
        _project_loop(loop, vertices, plane_origin, plane_normal) for loop in cap_loops
    ]
    if _has_nested_loops(projected_loops):
        raise ValueError("Cap triangulation does not support nested cut loops; try cap=False")
    faces: list[Face] = []
    for loop, projected in zip(cap_loops, projected_loops, strict=True):
        for a, b, c in _triangulate_loop(projected, tolerance):
            faces.append((loop[a], loop[c], loop[b]))
    return faces


def _contains_point(
    polygon: list[tuple[float, float]],
    point: tuple[float, float],
) -> bool:
    inside = False
    previous = len(polygon) - 1
    for index, current in enumerate(polygon):
        previous_point = polygon[previous]
        if ((current[1] > point[1]) != (previous_point[1] > point[1])) and (
            point[0]
            < (previous_point[0] - current[0])
            * (point[1] - current[1])
            / (previous_point[1] - current[1])
            + current[0]
        ):
            inside = not inside
        previous = index
    return inside


def _has_nested_loops(projected_loops: list[list[tuple[float, float]]]) -> bool:
    for index, loop in enumerate(projected_loops):
        for other_index, other_loop in enumerate(projected_loops):
            if index == other_index or not other_loop:
                continue
            if _contains_point(loop, other_loop[0]):
                return True
    return False


def _snapped_index(
    original: int,
    distance: float,
    on_plane: bool,
    origin: Point3Array,
    normal: Point3Array,
    vertices_list: list[Point3Array],
    projected_index: dict[int, int],
) -> int | None:
    if on_plane:
        return original
    if distance == 0.0:
        return original
    if original not in projected_index:
        projected = vertices_list[original] - normal * distance
        projected_index[original] = len(vertices_list)
        vertices_list.append(projected)
    return projected_index[original]


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


__all__ = [
    "close_boundary",
    "close_planar_cap",
    "close_to_plane",
    "coerce_mesh",
    "cut_mesh_by_plane",
]
