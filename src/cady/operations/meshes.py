"""Mesh construction, clipping, capping, topology, and loft helpers."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from math import ceil, cos, dist, pi, sin
from typing import TYPE_CHECKING, Literal, Protocol, TypeAlias, TypeGuard, cast

import numpy as np
from numpy.typing import NDArray

from cady.operations.coordinates import add3, scale3
from cady.operations.projections import (
    Point3Array,
    fit_plane_svd,
    max_plane_deviation,
    project_loop,
    unit3,
    vector3,
)
from cady.operations.sampling import Point2, segments_for_circle
from cady.operations.triangulation import Triangle2, dedupe_closed, triangulate_polygon
from cady.utils import finite, positive, positive_tolerance

if TYPE_CHECKING:
    from cady.geometry.mesh import Mesh3
    from cady.geometry.plane3 import Plane3
    from cady.geometry.surface import Surface3
    from cady.geometry.wireframe import Wireframe3

KeepSide = Literal["positive", "negative"]
Face = tuple[int, int, int]
Edge = tuple[int, int]
Segment = tuple[int, int]
Point3Tuple: TypeAlias = tuple[float, float, float]
Point3: TypeAlias = tuple[float, float, float]
Triangle3: TypeAlias = tuple[Point3Tuple, Point3Tuple, Point3Tuple]
FaceIndex = tuple[int, int, int]
EdgeIndex = tuple[int, int]
PointArray2 = NDArray[np.float64]
PointArray3 = NDArray[np.float64]
FaceArray = NDArray[np.int64]
EdgeArray = NDArray[np.int64]
MeshArrays = tuple[PointArray3, FaceArray, EdgeArray]


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


def _points2_array(value: object, *, name: str) -> PointArray2:
    array = _float_array(value, name=name)
    if array.ndim != 2:
        raise ValueError(f"{name} must have rank 2")
    if array.shape[1] != 2:
        raise ValueError(f"{name} must have shape (n, 2)")
    return array


def _points3_array(value: object, *, name: str) -> PointArray3:
    array = _float_array(value, name=name)
    if array.ndim != 2:
        raise ValueError(f"{name} must have rank 2")
    if array.shape[1] != 3:
        raise ValueError(f"{name} must have shape (n, 3)")
    return array


def boundary_edges(mesh: MeshArrays) -> list[Segment]:
    """Return edges that appear in exactly one face."""
    _vertices, faces, _edges = mesh
    counts: Counter[tuple[int, int]] = Counter()
    for face in faces:
        indices = [int(face[0]), int(face[1]), int(face[2])]
        for start, end in zip(indices, indices[1:] + indices[:1], strict=True):
            counts[(min(start, end), max(start, end))] += 1
    return [(a, b) for (a, b), count in counts.items() if count == 1]


def stitch_segments(segments: list[Segment]) -> list[list[int]]:
    """Stitch undirected boundary segments into simple vertex loops."""
    neighbours: dict[int, set[int]] = defaultdict(set)
    unused_edges: set[tuple[int, int]] = set()
    for start, end in segments:
        if start == end:
            continue
        edge = (min(start, end), max(start, end))
        if edge in unused_edges:
            continue
        unused_edges.add(edge)
        neighbours[start].add(end)
        neighbours[end].add(start)

    loops: list[list[int]] = []
    while unused_edges:
        start, second = next(iter(unused_edges))
        unused_edges.remove((start, second))
        loop = [start, second]
        previous = start
        current = second

        while current != start:
            candidates = [
                candidate
                for candidate in neighbours[current]
                if (min(current, candidate), max(current, candidate)) in unused_edges
                and candidate != previous
            ]
            if not candidates:
                break
            following = candidates[0]
            unused_edges.remove((min(current, following), max(current, following)))
            loop.append(following)
            previous, current = current, following

        if loop[-1] == start:
            loop.pop()
        if len(loop) >= 3 and loop[0] != loop[-1]:
            loops.append(loop)

    return loops

def triangulate_loop(points: list[tuple[float, float]], tolerance: float) -> list[Face]:
    """Triangulate a simple 2D loop with an ear-clipping pass."""
    if len(points) < 3:
        return []

    indices = list(range(len(points)))
    if _signed_area2(points) < 0.0:
        indices.reverse()

    triangles: list[Face] = []
    guard = 0
    while len(indices) > 3 and guard < len(points) * len(points):
        guard += 1
        clipped_ear = False
        for position, current in enumerate(indices):
            previous = indices[position - 1]
            following = indices[(position + 1) % len(indices)]
            a = points[previous]
            b = points[current]
            c = points[following]
            cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if cross <= tolerance:
                continue
            if any(
                candidate not in {previous, current, following}
                and _is_point_in_triangle(points[candidate], a, b, c, tolerance)
                for candidate in indices
            ):
                continue
            # Emit the ear in local loop index space and remove its tip.
            triangles.append((previous, current, following))
            del indices[position]
            clipped_ear = True
            break
        if not clipped_ear:
            raise ValueError("Could not triangulate cap loop; try cap=False")

    if len(indices) == 3:
        triangles.append((indices[0], indices[1], indices[2]))
    return triangles


def cap_loops_to_faces(
    vertices: list[Point3Array],
    cap_segments: list[Segment],
    plane_origin: Point3Array,
    plane_normal: Point3Array,
    *,
    tolerance: float,
) -> list[Face]:
    """Triangulate cap loops from boundary segments on a plane."""
    if not cap_segments:
        return []
    cap_loops = stitch_segments(cap_segments)
    projected_loops = [
        project_loop(loop, vertices, plane_origin, plane_normal) for loop in cap_loops
    ]
    if _has_nested_loops(projected_loops):
        raise ValueError("Cap triangulation does not support nested cut loops; try cap=False")
    faces: list[Face] = []
    for loop, projected in zip(cap_loops, projected_loops, strict=True):
        for a, b, c in triangulate_loop(projected, tolerance):
            faces.append((loop[a], loop[c], loop[b]))
    return faces


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
    """Cap an open mesh at an explicit plane.

    Detects boundary edges on the plane, stitches them into loops, and
    triangulates each loop. Returns a new mesh with the cap faces added.

    When *snap_tolerance* is ``None`` (default), only boundary edges whose
    vertices lie on the plane (within *tolerance*) are capped.

    When *snap_tolerance* is set, boundary vertices within that distance of
    the plane (but outside *tolerance*) are projected onto the plane: new
    projected vertices are appended and used for the cap, while the original
    vertices stay connected to the mesh body. The resulting thin gaps between
    the original boundary and the projected cap become new boundary edges that
    ``close_boundary`` can fill.
    """
    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive")
    if snap_tolerance is not None and snap_tolerance <= 0.0:
        raise ValueError("snap_tolerance must be positive")
    if plane_origin is None or plane_normal is None:
        raise TypeError("plane_origin and plane_normal are required")
    mesh = coerce_mesh(mesh_or_vertices, faces, edges)
    vertices, mesh_faces, mesh_edges = mesh
    origin = vector3(plane_origin, name="plane_origin")
    normal = unit3(plane_normal, name="plane_normal")

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
            cap_a = _snapped_index(
                a, dist_a, on_a, origin, normal, vertices_list, projected_index
            )
            cap_b = _snapped_index(
                b, dist_b, on_b, origin, normal, vertices_list, projected_index
            )
            if cap_a is not None and cap_b is not None:
                plane_segments.append((cap_a, cap_b))

    if not plane_segments:
        return mesh

    cap_faces = cap_loops_to_faces(
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
    """Close all planar boundary holes in a mesh.

    Detects boundary edges, stitches them into loops, fits a best-fit plane
    to each loop via SVD, and triangulates planar loops. Raises
    ``ValueError`` if any boundary loop is non-planar.
    """
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
        loop_origin, loop_normal = fit_plane_svd(loop_points)
        deviation = max_plane_deviation(loop_points, loop_origin, loop_normal)
        if deviation > tolerance:
            raise ValueError(
                f"Boundary loop is non-planar (max deviation {deviation:.3e} > "
                f"tolerance {tolerance:.3e}); "
                "close_holes is not implemented - use close_boundary for planar holes only"
            )
        projected = project_loop(loop, vertices_list, loop_origin, loop_normal)
        all_cap_faces.extend(
            (loop[a], loop[c], loop[b]) for a, b, c in triangulate_loop(projected, tolerance)
        )

    if not all_cap_faces:
        return mesh

    all_faces = np.vstack([faces_array] + [np.array(all_cap_faces, dtype=np.int64)]).astype(
        np.int64, copy=False
    )
    return vertices, all_faces, mesh_edges


def _signed_area2(points: list[tuple[float, float]]) -> float:
    return 0.5 * sum(
        start[0] * end[1] - end[0] * start[1]
        for start, end in zip(points, points[1:] + points[:1], strict=True)
    )


def _is_point_in_triangle(
    point: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    tolerance: float,
) -> bool:
    def cross2(
        start: tuple[float, float],
        end: tuple[float, float],
        test: tuple[float, float],
    ) -> float:
        return (end[0] - start[0]) * (test[1] - start[1]) - (end[1] - start[1]) * (
            test[0] - start[0]
        )

    return (
        cross2(a, b, point) >= -tolerance
        and cross2(b, c, point) >= -tolerance
        and cross2(c, a, point) >= -tolerance
    )


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
    """Return the index to use for a cap vertex.

    If the original vertex is already on the plane return its original index.
    Otherwise project it, add the projection to *vertices_list* once, and
    return the new index.
    """
    if on_plane:
        return original
    if distance == 0.0:
        return original
    if original not in projected_index:
        projected = vertices_list[original] - normal * distance
        projected_index[original] = len(vertices_list)
        vertices_list.append(projected)
    return projected_index[original]


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

    mesh = coerce_mesh(mesh_or_vertices, faces)
    vertices, mesh_faces, _mesh_edges = mesh
    origin = vector3(plane_origin, name="plane_origin")
    normal = unit3(plane_normal, name="plane_normal")
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
    u = (
        (1.0, 0.0, 0.0)
        if abs(w[2]) == 1
        else _normalised(_cross((0.0, 0.0, 1.0), w))
    )
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


def boundary_edges_from_faces(faces: Sequence[FaceIndex]) -> tuple[EdgeIndex, ...]:
    """Return undirected edges referenced by exactly one triangle."""
    counts: dict[EdgeIndex, int] = {}
    for a, b, c in faces:
        for start, end in ((a, b), (b, c), (c, a)):
            edge = (min(start, end), max(start, end))
            counts[edge] = counts.get(edge, 0) + 1
    return tuple(edge for edge, count in counts.items() if count == 1)


def prune_dangling_edges(edges: Sequence[EdgeIndex]) -> tuple[EdgeIndex, ...]:
    """Repeatedly remove degree-1 edges until only cycles remain."""
    live_edges = list(edges)
    live_vertices = {index for edge in live_edges for index in edge}

    while live_edges:
        degrees = {index: 0 for index in live_vertices}
        for a, b in live_edges:
            degrees[a] = degrees.get(a, 0) + 1
            degrees[b] = degrees.get(b, 0) + 1

        dangling = {index for index, degree in degrees.items() if degree == 1}
        if not dangling:
            break

        live_vertices.difference_update(dangling)
        live_edges = [
            (a, b)
            for a, b in live_edges
            if a in live_vertices and b in live_vertices
        ]

    return tuple(live_edges)


def project_point_to_plane(
    point: Point3,
    distance: float,
    normal: np.ndarray,
) -> Point3:
    """Project a point along a plane normal by a signed distance."""
    return (
        point[0] - distance * float(normal[0]),
        point[1] - distance * float(normal[1]),
        point[2] - distance * float(normal[2]),
    )


def compact_mesh_data(
    vertices: Sequence[Point3],
    faces: Sequence[FaceIndex],
    edges: Sequence[EdgeIndex],
) -> tuple[tuple[Point3, ...], tuple[FaceIndex, ...], tuple[EdgeIndex, ...]]:
    """Drop unused vertices and remap faces and edges into a dense index space."""
    used_vertices = {index for face in faces for index in face}
    used_vertices.update(index for edge in edges for index in edge)
    if not used_vertices:
        return (), (), ()

    ordered_vertices = tuple(sorted(used_vertices))
    remap = {old: new for new, old in enumerate(ordered_vertices)}
    compact_vertices = tuple(vertices[index] for index in ordered_vertices)
    compact_faces = tuple((remap[a], remap[b], remap[c]) for a, b, c in faces)
    compact_edges = tuple((remap[a], remap[b]) for a, b in edges)
    return compact_vertices, compact_faces, compact_edges


@dataclass(frozen=True, slots=True)
class LoftMesh:
    """Simple loft result containing vertices, faces, and sampled edges."""

    vertices: tuple[Point3, ...]
    faces: tuple[Face, ...]
    edges: tuple[Edge, ...]


def loft_section_polylines(
    polylines: Iterable[Sequence[Point3]],
    *,
    tolerance: float,
) -> LoftMesh | None:
    """Loft open section polylines into a coarse strip mesh, if possible."""
    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive")

    sections = _section_curves(polylines, tolerance=tolerance)
    if len(sections) < 2:
        return None

    sample_count = min(max(len(vertices) for _x, vertices in sections), 96)
    if sample_count < 2:
        return None

    rows = tuple(
        _resample_polyline(_orient_section(vertices), sample_count)
        for _x, vertices in sections
    )
    vertices = tuple(point for row in rows for point in row)
    faces: list[Face] = []
    edges: set[Edge] = set()

    for section_index in range(len(rows)):
        row_start = section_index * sample_count
        for sample_index in range(sample_count - 1):
            edges.add((row_start + sample_index, row_start + sample_index + 1))

    for section_index in range(len(rows) - 1):
        left_start = section_index * sample_count
        right_start = (section_index + 1) * sample_count
        for sample_index in range(sample_count):
            edges.add((left_start + sample_index, right_start + sample_index))
        for sample_index in range(sample_count - 1):
            a = left_start + sample_index
            b = right_start + sample_index
            c = left_start + sample_index + 1
            d = right_start + sample_index + 1
            _append_face_if_valid(faces, vertices, (a, b, d), tolerance)
            _append_face_if_valid(faces, vertices, (a, d, c), tolerance)

    if not faces:
        return None
    return LoftMesh(vertices, tuple(faces), tuple(sorted(edges)))


def _section_curves(
    polylines: Iterable[Sequence[Point3]],
    *,
    tolerance: float,
) -> tuple[tuple[float, tuple[Point3, ...]], ...]:
    x_tolerance = max(tolerance, 1e-3)
    grouped: dict[int, list[tuple[float, tuple[Point3, ...]]]] = {}
    for polyline in polylines:
        vertices = tuple((float(x), float(y), float(z)) for x, y, z in polyline)
        if len(vertices) < 4:
            continue
        xs = [point[0] for point in vertices]
        ys = [point[1] for point in vertices]
        zs = [point[2] for point in vertices]
        if max(xs) - min(xs) > x_tolerance:
            continue
        if max(ys) - min(ys) <= x_tolerance or max(zs) - min(zs) <= x_tolerance:
            continue
        length = _polyline_length(vertices)
        if length <= x_tolerance:
            continue
        x = sum(xs) / len(xs)
        grouped.setdefault(round(x / x_tolerance), []).append((length, vertices))

    sections: list[tuple[float, tuple[Point3, ...]]] = []
    for group in grouped.values():
        # Keep the longest candidate in each x-station bucket as the representative section.
        _length, vertices = max(group, key=lambda item: item[0])
        x = sum(point[0] for point in vertices) / len(vertices)
        sections.append((x, vertices))
    return tuple(sorted(sections, key=lambda item: item[0]))


def _orient_section(vertices: tuple[Point3, ...]) -> tuple[Point3, ...]:
    if vertices[0][2] > vertices[-1][2]:
        return tuple(reversed(vertices))
    return vertices


def _resample_polyline(vertices: tuple[Point3, ...], count: int) -> tuple[Point3, ...]:
    if count < 2:
        raise ValueError("count must be at least 2")
    distances = [0.0]
    for previous, current in zip(vertices, vertices[1:], strict=False):
        distances.append(distances[-1] + dist(previous, current))
    total = distances[-1]
    if total == 0.0:
        return tuple(vertices[0] for _ in range(count))

    sampled: list[Point3] = []
    segment_index = 0
    for sample_index in range(count):
        target = total * sample_index / (count - 1)
        while segment_index < len(distances) - 2 and distances[segment_index + 1] < target:
            segment_index += 1
        start = vertices[segment_index]
        end = vertices[segment_index + 1]
        start_distance = distances[segment_index]
        segment_length = distances[segment_index + 1] - start_distance
        ratio = 0.0 if segment_length == 0.0 else (target - start_distance) / segment_length
        sampled.append(
            (
                start[0] + (end[0] - start[0]) * ratio,
                start[1] + (end[1] - start[1]) * ratio,
                start[2] + (end[2] - start[2]) * ratio,
            )
        )
    return tuple(sampled)


def _polyline_length(vertices: tuple[Point3, ...]) -> float:
    return sum(
        dist(previous, current)
        for previous, current in zip(vertices, vertices[1:], strict=False)
    )


def _append_face_if_valid(
    faces: list[Face],
    vertices: tuple[Point3, ...],
    face: Face,
    tolerance: float,
) -> None:
    a, b, c = (vertices[index] for index in face)
    if dist(a, b) <= tolerance or dist(b, c) <= tolerance or dist(c, a) <= tolerance:
        return
    faces.append(face)


class _SourceCurveLike(Protocol):
    vertices: Iterable[Point3]
    layer: str | None
    source_index: int
    entity_type: str


@dataclass(frozen=True, slots=True)
class LinesplanCurve:
    """Normalised source curve record used by linesplan operations."""

    vertices: tuple[Point3, ...]
    layer: str | None = None
    source_index: int = 0
    entity_type: str = "POLYLINE"

    def __init__(
        self,
        vertices: Iterable[Point3],
        *,
        layer: str | None = None,
        source_index: int = 0,
        entity_type: str = "POLYLINE",
    ) -> None:
        object.__setattr__(self, "vertices", tuple(vertices))
        object.__setattr__(self, "layer", layer)
        object.__setattr__(self, "source_index", int(source_index))
        object.__setattr__(self, "entity_type", entity_type)


@dataclass(frozen=True, slots=True)
class RejectedLinesplanCurve:
    """Source curve that could not be classified into the network."""

    curve: LinesplanCurve
    reason: str


@dataclass(frozen=True, slots=True)
class GuideCoverage:
    """Coverage of one guide curve across ordered section stations."""

    guide_kind: str
    curve: LinesplanCurve
    matched_sections: tuple[int, ...]
    missing_sections: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class CompatibilityReport:
    """Summary of whether a classified linesplan can be meshed reliably."""

    section_count: int
    buttock_count: int
    waterline_count: int
    knuckle_count: int
    guide_coverages: tuple[GuideCoverage, ...]
    issues: tuple[str, ...]

    @property
    def is_compatible(self) -> bool:
        return not self.issues


@dataclass(frozen=True, slots=True)
class LinesplanNetwork:
    """Grouped linesplan curves and the report derived from them."""

    sections: tuple[LinesplanCurve, ...]
    buttocks: tuple[LinesplanCurve, ...]
    waterlines: tuple[LinesplanCurve, ...]
    knuckles: tuple[LinesplanCurve, ...]
    rejected: tuple[RejectedLinesplanCurve, ...]
    compatibility_report: CompatibilityReport


def classify_linesplan_curves(
    curves: Iterable[object] | Wireframe3,
    *,
    tolerance: float,
) -> LinesplanNetwork:
    """Group source curves into sections, buttocks, waterlines, and knuckles."""
    if tolerance <= 0:
        raise ValueError("tolerance must be positive")

    source_curves = _source_curves(curves)
    sections: list[LinesplanCurve] = []
    buttocks: list[LinesplanCurve] = []
    waterlines: list[LinesplanCurve] = []
    knuckles: list[LinesplanCurve] = []
    rejected: list[RejectedLinesplanCurve] = []

    for curve in source_curves:
        if len(curve.vertices) < 2:
            rejected.append(RejectedLinesplanCurve(curve, "curve has fewer than two vertices"))
            continue
        kind, reason = _classify_curve(curve, tolerance)
        if kind == "section":
            sections.append(curve)
        elif kind == "buttock":
            buttocks.append(curve)
        elif kind == "waterline":
            waterlines.append(curve)
        elif kind == "knuckle":
            knuckles.append(curve)
        else:
            rejected.append(RejectedLinesplanCurve(curve, reason))

    sections_tuple = tuple(sorted(sections, key=_station_x))
    buttocks_tuple = tuple(buttocks)
    waterlines_tuple = tuple(waterlines)
    knuckles_tuple = tuple(knuckles)
    return LinesplanNetwork(
        sections_tuple,
        buttocks_tuple,
        waterlines_tuple,
        knuckles_tuple,
        tuple(rejected),
        _compatibility_report(
            sections_tuple,
            buttocks_tuple,
            waterlines_tuple,
            knuckles_tuple,
            tolerance,
        ),
    )


def mesh_linesplan_network(
    network: LinesplanNetwork,
    *,
    tolerance: float,
    samples_per_curve: int = 12,
) -> Mesh3:
    """Build a simple quad-strip mesh across classified section curves."""
    from cady.geometry.mesh import Mesh3

    if tolerance <= 0:
        raise ValueError("tolerance must be positive")
    if samples_per_curve < 2:
        raise ValueError("samples_per_curve must be at least 2")

    sections = _merged_sections(network.sections, tolerance)
    if len(sections) < 2:
        raise ValueError("linesplan network requires at least two section curves")

    sample_values = _sample_values(sections, network, samples_per_curve, tolerance)
    rows = [[_point_on_section(section, value) for value in sample_values] for section in sections]

    vertices = tuple(point for row in rows for point in row)
    width = len(sample_values)
    faces: list[tuple[int, int, int]] = []
    for row in range(len(rows) - 1):
        for col in range(width - 1):
            a = row * width + col
            b = (row + 1) * width + col
            c = (row + 1) * width + col + 1
            d = row * width + col + 1
            faces.extend(((a, b, c), (a, c, d)))

    edge_set: set[tuple[int, int]] = set()
    for row in range(len(rows)):
        for col in range(width - 1):
            start = row * width + col
            edge_set.add((start, start + 1))
    for row in range(len(rows) - 1):
        for col in range(width):
            start = row * width + col
            edge_set.add((start, start + width))
    return Mesh3(vertices, tuple(faces), tuple(sorted(edge_set)))


def _source_curves(curves: Iterable[object] | Wireframe3) -> tuple[LinesplanCurve, ...]:
    from cady.geometry.wireframe import Wireframe3

    if isinstance(curves, Wireframe3):
        return tuple(
            LinesplanCurve((curves.vertices[vertex] for vertex in path), source_index=index)
            for index, path in enumerate(_wireframe_paths(curves))
        )
    result: list[LinesplanCurve] = []
    for index, curve in enumerate(curves):
        source = cast(_SourceCurveLike, curve)
        result.append(
            LinesplanCurve(
                source.vertices,
                layer=getattr(source, "layer", None),
                source_index=getattr(source, "source_index", index),
                entity_type=getattr(source, "entity_type", "POLYLINE"),
            )
        )
    return tuple(result)


def _wireframe_paths(wireframe: Wireframe3) -> tuple[tuple[int, ...], ...]:
    adjacency: dict[int, list[int]] = {}
    for start, end in wireframe.edges:
        adjacency.setdefault(start, []).append(end)
        adjacency.setdefault(end, []).append(start)

    visited_edges: set[tuple[int, int]] = set()
    paths: list[tuple[int, ...]] = []
    starts = sorted(adjacency, key=lambda vertex: (len(adjacency[vertex]) != 1, vertex))
    for start in starts:
        for neighbour in sorted(adjacency[start]):
            edge = (min(start, neighbour), max(start, neighbour))
            if edge in visited_edges:
                continue
            path = [start, neighbour]
            visited_edges.add(edge)
            previous, current = start, neighbour
            while True:
                # Continue only through unambiguous degree-2 runs; branching stays split.
                candidates = [
                    vertex
                    for vertex in sorted(adjacency[current])
                    if vertex != previous
                    and (min(current, vertex), max(current, vertex)) not in visited_edges
                ]
                if len(candidates) != 1:
                    break
                next_vertex = candidates[0]
                visited_edges.add((min(current, next_vertex), max(current, next_vertex)))
                path.append(next_vertex)
                previous, current = current, next_vertex
            paths.append(tuple(path))
    return tuple(paths)


def _classify_curve(curve: LinesplanCurve, tolerance: float) -> tuple[str | None, str]:
    layer = (curve.layer or "").strip().upper()
    if layer and layer != "0":
        if layer in {"SECTION", "SECTIONS", "STATION", "STATIONS"}:
            return "section", ""
        if layer in {"BUTTOCK", "BUTTOCKS"}:
            return "buttock", ""
        if layer in {"WATERLINE", "WATERLINES"}:
            return "waterline", ""
        if layer in {"KNUCKLE", "KNUCKLES"}:
            return "knuckle", ""
        return None, f"unrecognised linesplan layer {curve.layer!r}"

    constants = [
        ("section", _span([point[0] for point in curve.vertices]) <= tolerance),
        ("buttock", _span([point[1] for point in curve.vertices]) <= tolerance),
        ("waterline", _span([point[2] for point in curve.vertices]) <= tolerance),
    ]
    matches = [kind for kind, matched in constants if matched]
    if len(matches) == 1:
        return matches[0], ""
    return None, "fallback orientation is ambiguous"


def _compatibility_report(
    sections: tuple[LinesplanCurve, ...],
    buttocks: tuple[LinesplanCurve, ...],
    waterlines: tuple[LinesplanCurve, ...],
    knuckles: tuple[LinesplanCurve, ...],
    tolerance: float,
) -> CompatibilityReport:
    coverages: list[GuideCoverage] = []
    issues: list[str] = []
    for kind, guides in (
        ("buttock", buttocks),
        ("waterline", waterlines),
        ("knuckle", knuckles),
    ):
        for guide in guides:
            matched = tuple(
                index
                for index, section in enumerate(sections)
                if _guide_matches_section(guide, section, tolerance)
            )
            missing = tuple(index for index in range(len(sections)) if index not in matched)
            coverages.append(GuideCoverage(kind, guide, matched, missing))
            if missing:
                issues.append(
                    f"{kind} curve {guide.source_index} intersects "
                    f"{len(matched)}/{len(sections)} sections within tolerance"
                )
    return CompatibilityReport(
        len(sections),
        len(buttocks),
        len(waterlines),
        len(knuckles),
        tuple(coverages),
        tuple(issues),
    )


def _guide_matches_section(
    guide: LinesplanCurve,
    section: LinesplanCurve,
    tolerance: float,
) -> bool:
    station = _station_x(section)
    return any(abs(point[0] - station) <= tolerance for point in guide.vertices)


def _merged_sections(
    sections: tuple[LinesplanCurve, ...],
    tolerance: float,
) -> tuple[tuple[Point3, ...], ...]:
    by_station: dict[float, list[Point3]] = {}
    for section in sections:
        station = _station_x(section)
        key = next((value for value in by_station if abs(value - station) <= tolerance), station)
        by_station.setdefault(key, []).extend(section.vertices)

    merged: list[tuple[Point3, ...]] = []
    for _station, points in sorted(by_station.items()):
        useful = [
            point
            for point in points
            if _span([p[1] for p in points]) > tolerance or point[1] < 10.0
        ]
        deduped = _dedupe_points(useful, tolerance)
        merged.append(
            tuple(sorted(deduped, key=lambda point: (point[1], point[2], point[0])))
        )
    return tuple(section for section in merged if len(section) >= 2)


def _sample_values(
    sections: tuple[tuple[Point3, ...], ...],
    network: LinesplanNetwork,
    samples_per_curve: int,
    tolerance: float,
) -> tuple[float, ...]:
    max_y = min(max(point[1] for point in section) for section in sections)
    values = {max_y * index / (samples_per_curve - 1) for index in range(samples_per_curve)}
    for guide in network.buttocks + network.waterlines + network.knuckles:
        if _span([point[0] for point in guide.vertices]) > tolerance:
            for point in guide.vertices:
                if 0.0 <= point[1] <= max_y:
                    values.add(point[1])
    return tuple(sorted(values))


def _point_on_section(section: tuple[Point3, ...], y_value: float) -> Point3:
    for left, right in zip(section, section[1:], strict=False):
        if min(left[1], right[1]) <= y_value <= max(left[1], right[1]):
            span = right[1] - left[1]
            ratio = 0.0 if span == 0.0 else (y_value - left[1]) / span
            return (
                left[0] + (right[0] - left[0]) * ratio,
                y_value,
                left[2] + (right[2] - left[2]) * ratio,
            )
    nearest = min(section, key=lambda point: abs(point[1] - y_value))
    return (nearest[0], y_value, nearest[2])


def _dedupe_points(points: Iterable[Point3], tolerance: float) -> tuple[Point3, ...]:
    result: list[Point3] = []
    for point in points:
        if not any(
            abs(point[0] - other[0]) <= tolerance
            and abs(point[1] - other[1]) <= tolerance
            and abs(point[2] - other[2]) <= tolerance
            for other in result
        ):
            result.append(point)
    return tuple(result)


def _station_x(section: LinesplanCurve | tuple[Point3, ...]) -> float:
    vertices = section.vertices if isinstance(section, LinesplanCurve) else section
    return sum(point[0] for point in vertices) / len(vertices)


def _span(values: Iterable[float]) -> float:
    values_tuple = tuple(values)
    return max(values_tuple) - min(values_tuple)


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


def region_mesh(region: object, plane: Plane3, *, tolerance: float) -> Mesh3:
    from cady.geometry.surface import Surface3

    return surface_region_mesh(region, Surface3.plane(plane=plane), tolerance=tolerance)


def surface_region_mesh(region: object, surface: Surface3, *, tolerance: float) -> Mesh3:
    loops = region_loops_from_region(region, tolerance=tolerance)
    outer, holes = _outer_and_holes(loops)
    cap_triangles = triangulate_polygon(
        outer,
        holes,
        tolerance=tolerance,
    )
    triangles = tuple(
        (surface.point(*a), surface.point(*b), surface.point(*c))
        for a, b, c in cap_triangles
    )
    return mesh_from_triangles(triangles)


def extrusion_mesh(
    region: object,
    plane: Plane3,
    *,
    distance: float,
    tolerance: float,
) -> Mesh3:
    from cady.geometry.plane3 import Plane3

    distance = finite(distance, "distance")
    if distance == 0.0:
        raise ValueError("distance must be finite and non-zero")
    loops = region_loops_from_region(region, tolerance=tolerance)
    outer, holes = _outer_and_holes(loops)
    cap_triangles = triangulate_polygon(
        outer,
        holes,
        tolerance=tolerance,
    )
    end_origin = add3(plane.origin, scale3(plane.normal, distance))
    end_plane = Plane3(end_origin, plane.x_axis, plane.normal)
    triangles: list[Triangle3] = []
    for a, b, c in cap_triangles:
        triangles.append((plane.point(*c), plane.point(*b), plane.point(*a)))
        triangles.append((end_plane.point(*a), end_plane.point(*b), end_plane.point(*c)))
    for loop, is_hole in loops:
        points = dedupe_closed(loop)
        for a, b in zip(points, points[1:] + points[:1], strict=True):
            a0 = plane.point(*a)
            b0 = plane.point(*b)
            a1 = end_plane.point(*a)
            b1 = end_plane.point(*b)
            if is_hole:
                triangles.append((a0, b1, b0))
                triangles.append((a0, a1, b1))
            else:
                triangles.append((a0, b0, b1))
                triangles.append((a0, b1, a1))
    return mesh_from_triangles(tuple(triangles))


def region_loops_from_region(
    region: object,
    *,
    tolerance: float,
) -> tuple[tuple[tuple[Point2, ...], bool], ...]:
    tolerance = validate_tolerance(tolerance)
    loops_method = getattr(region, "loops", None)
    if callable(loops_method):
        raw_loops = cast(Iterable[object], loops_method(tolerance=tolerance))
        loops: tuple[object, ...] = tuple(raw_loops)
        if not loops:
            raise ValueError("region must provide at least one closed loop")
        return tuple(
            (_points_from_closed_polyline(loop, label), is_hole)
            for label, loop, is_hole in _labelled_loops(loops)
        )

    to_array = getattr(region, "to_array", None)
    if to_array is None:
        raise TypeError("region must provide to_array(tolerance=...)")
    loop = to_array(tolerance=tolerance)
    return ((_points_from_closed_polyline(loop, "outer"), False),)


def mesh_from_triangles(triangles: tuple[Triangle3, ...]) -> Mesh3:
    from cady.geometry.mesh import Mesh3

    vertices: list[Point3] = []
    faces: list[tuple[int, int, int]] = []
    for triangle in triangles:
        start = len(vertices)
        vertices.extend(triangle)
        faces.append((start, start + 1, start + 2))
    return Mesh3(tuple(vertices), tuple(faces))


def _points2(points: object) -> tuple[Point2, ...]:
    array = _points2_array(points, name="vertices")
    return tuple((float(point[0]), float(point[1])) for point in array)


def _labelled_loops(
    loops: tuple[object, ...],
) -> tuple[tuple[str, object, bool], ...]:
    labelled = [("outer", loops[0], False)]
    labelled.extend((f"holes[{index}]", loop, True) for index, loop in enumerate(loops[1:]))
    return tuple(labelled)


def _points_from_closed_polyline(loop: object, label: str) -> tuple[Point2, ...]:
    vertices = getattr(loop, "vertices", loop)
    closed = getattr(loop, "closed", True)
    if not closed:
        raise ValueError(f"region {label} boundary must be closed")
    points = dedupe_closed(_points2(vertices))
    if len(points) < 3:
        raise ValueError(f"region {label} boundary must contain at least three points")
    return points


def _outer_and_holes(
    loops: tuple[tuple[tuple[Point2, ...], bool], ...],
) -> tuple[tuple[Point2, ...], tuple[tuple[Point2, ...], ...]]:
    outer = loops[0][0]
    holes = tuple(loop for loop, is_hole in loops[1:] if is_hole)
    return outer, holes
