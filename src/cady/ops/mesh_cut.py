from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from cady.numeric.mesh3d import ArrayMesh3

KeepSide = Literal["positive", "negative"]
Point3Array = NDArray[np.float64]
Face = tuple[int, int, int]
Segment = tuple[int, int]


def vector3(value: object, *, name: str) -> Point3Array:
    array = np.array(value, dtype=np.float64, copy=True)
    if array.shape != (3,) or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a finite 3D vector")
    return array


def unit3(value: object, *, name: str) -> Point3Array:
    vector = vector3(value, name=name)
    length = float(np.linalg.norm(vector))
    if length == 0.0:
        raise ValueError(f"{name} must be non-zero")
    return vector / length


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
    polygon: Iterable[Point3Array],
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


def basis_for_plane(normal: Point3Array) -> tuple[Point3Array, Point3Array]:
    reference = (
        np.array([1.0, 0.0, 0.0], dtype=np.float64)
        if abs(float(normal[0])) < 0.9
        else np.array([0.0, 1.0, 0.0], dtype=np.float64)
    )
    u_axis = np.cross(normal, reference)
    u_axis = u_axis / np.linalg.norm(u_axis)
    v_axis = np.cross(normal, u_axis)
    return u_axis, v_axis


def project_loop(
    loop: list[int],
    vertices: list[Point3Array],
    origin: Point3Array,
    normal: Point3Array,
) -> list[tuple[float, float]]:
    u_axis, v_axis = basis_for_plane(normal)
    projected: list[tuple[float, float]] = []
    for vertex_index in loop:
        relative = vertices[vertex_index] - origin
        projected.append((float(np.dot(relative, u_axis)), float(np.dot(relative, v_axis))))
    return projected


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


def triangulate_loop(points: list[tuple[float, float]], tolerance: float) -> list[Face]:
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
            triangles.append((previous, current, following))
            del indices[position]
            clipped_ear = True
            break
        if not clipped_ear:
            raise ValueError("Could not triangulate cap loop; try cap=False")

    if len(indices) == 3:
        triangles.append((indices[0], indices[1], indices[2]))
    return triangles


def stitch_segments(segments: list[Segment]) -> list[list[int]]:
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


def _cap_loops_to_faces(
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


def _boundary_edges(mesh: ArrayMesh3) -> list[Segment]:
    """Return edges that appear in exactly one face."""
    from collections import Counter

    counts: Counter[tuple[int, int]] = Counter()
    for face in mesh.faces:
        indices = [int(face[0]), int(face[1]), int(face[2])]
        for start, end in zip(indices, indices[1:] + indices[:1], strict=True):
            counts[(min(start, end), max(start, end))] += 1
    return [(a, b) for (a, b), count in counts.items() if count == 1]


def fit_plane_svd(points: Point3Array) -> tuple[Point3Array, Point3Array]:
    """Fit a plane to points via SVD. Returns (origin, normal)."""
    centroid = points.mean(axis=0)
    centered = points - centroid
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    normal = vt[-1]
    if float(np.dot(normal, np.array([0.0, 0.0, 1.0]))) < 0.0:
        normal = -normal
    return centroid, normal


def max_plane_deviation(points: Point3Array, origin: Point3Array, normal: Point3Array) -> float:
    """Return the maximum absolute distance of points from the plane."""
    return float(np.max(np.abs(np.dot(points - origin, normal))))


def cut_mesh_by_plane(
    mesh: ArrayMesh3,
    plane_origin: object,
    plane_normal: object,
    *,
    keep: KeepSide = "positive",
    cap: bool = True,
    tolerance: float = 1e-9,
) -> ArrayMesh3:
    """Return the part of a triangle mesh on one side of a plane.

    The positive side is where ``dot(point - plane_origin, plane_normal) >= 0``.
    Set ``keep="negative"`` to retain the opposite half-space. When ``cap`` is
    true, the cut boundary is filled for simple non-nested loops.
    """
    if keep not in {"positive", "negative"}:
        raise ValueError("keep must be 'positive' or 'negative'")
    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive")

    origin = vector3(plane_origin, name="plane_origin")
    normal = unit3(plane_normal, name="plane_normal")
    if keep == "negative":
        normal = -normal

    output_vertices: list[Point3Array] = []
    output_faces: list[Face] = []
    index_by_key: dict[tuple[int, int, int], int] = {}
    cap_segments: list[Segment] = []

    source_triangles = np.asarray(mesh.triangles, dtype=np.float64)
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
        return ArrayMesh3(
            np.empty((0, 3), dtype=np.float64),
            np.empty((0, 3), dtype=np.int64),
        )

    return ArrayMesh3(
        np.array(output_vertices, dtype=np.float64),
        np.array(output_faces, dtype=np.int64),
    )


def close_planar_cap(
    mesh: ArrayMesh3,
    plane_origin: object,
    plane_normal: object,
    *,
    tolerance: float = 1e-9,
    snap_tolerance: float | None = None,
) -> ArrayMesh3:
    """Cap an open mesh at an explicit plane.

    Detects boundary edges on the plane, stitches them into loops, and
    triangulates each loop. Returns a new mesh with the cap faces added.

    When *snap_tolerance* is ``None`` (default), only boundary edges whose
    vertices lie on the plane (within *tolerance*) are capped.

    When *snap_tolerance* is set, boundary vertices within that distance of
    the plane (but outside *tolerance*) are projected onto the plane: new
    projected vertices are appended and used for the cap, while the original
    vertices stay connected to the mesh body.  The resulting thin gaps between
    the original boundary and the projected cap become new boundary edges that
    ``close_boundary`` can fill.
    """
    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive")
    if snap_tolerance is not None and snap_tolerance <= 0.0:
        raise ValueError("snap_tolerance must be positive")
    origin = vector3(plane_origin, name="plane_origin")
    normal = unit3(plane_normal, name="plane_normal")

    vertices_np = mesh.vertices.astype(np.float64, copy=False)
    if len(vertices_np) == 0:
        return mesh

    boundary = _boundary_edges(mesh)
    if not boundary:
        return mesh

    # Build the extended vertex list so we can append projected copies.
    vertices_list: list[Point3Array] = [
        np.array(vertex, dtype=np.float64, copy=True) for vertex in vertices_np
    ]

    # Map original vertex index → projected-copy index (one copy per vertex).
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

    # If we added projected vertices, the returned vertex array must include them.
    out_vertices = mesh.vertices
    if projected_index:
        out_vertices = np.array(vertices_list, dtype=np.float64)

    all_faces = np.vstack([mesh.faces] + [np.array(cap_faces, dtype=np.int64)]).astype(
        np.int64, copy=False
    )
    return ArrayMesh3(out_vertices, all_faces, mesh.edges)


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
    Otherwise project it, add the projection to *vertices_list* (once), and
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


def close_boundary(
    mesh: ArrayMesh3,
    *,
    tolerance: float = 1e-9,
) -> ArrayMesh3:
    """Close all planar boundary holes in a mesh.

    Detects boundary edges, stitches them into loops, fits a best-fit plane
    to each loop via SVD, and triangulates planar loops. Raises
    ``ValueError`` if any boundary loop is non-planar.
    """
    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive")

    boundary = _boundary_edges(mesh)
    if not boundary:
        return mesh

    vertices_np = mesh.vertices.astype(np.float64, copy=False)
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
                "close_holes is not implemented — use close_boundary for planar holes only"
            )
        projected = project_loop(loop, vertices_list, loop_origin, loop_normal)
        all_cap_faces.extend(
            (loop[a], loop[c], loop[b]) for a, b, c in triangulate_loop(projected, tolerance)
        )

    if not all_cap_faces:
        return mesh

    all_faces = np.vstack([mesh.faces] + [np.array(all_cap_faces, dtype=np.int64)]).astype(
        np.int64, copy=False
    )
    return ArrayMesh3(mesh.vertices, all_faces, mesh.edges)
