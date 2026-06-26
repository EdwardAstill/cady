from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from cady.operations._mesh_arrays import coerce_mesh, return_mesh
from cady.operations.arrays3d import ArrayMesh3
from cady.operations.mesh_boundaries import Segment, boundary_edges, stitch_segments
from cady.operations.planes import (
    Point3Array,
    fit_plane_svd,
    max_plane_deviation,
    project_loop,
    unit3,
    vector3,
)

Face = tuple[int, int, int]


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
    mesh_or_vertices: ArrayMesh3 | object,
    faces: object | None = None,
    edges: object | None = None,
    plane_origin: object | None = None,
    plane_normal: object | None = None,
    *,
    tolerance: float = 1e-9,
    snap_tolerance: float | None = None,
) -> ArrayMesh3 | tuple[NDArray[np.float64], NDArray[np.int64], NDArray[np.int64]]:
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
    mesh, as_tuple = coerce_mesh(mesh_or_vertices, faces, edges)
    origin = vector3(plane_origin, name="plane_origin")
    normal = unit3(plane_normal, name="plane_normal")

    vertices_np = mesh.vertices.astype(np.float64, copy=False)
    if len(vertices_np) == 0:
        return return_mesh(mesh, as_tuple)

    boundary = boundary_edges(mesh)
    if not boundary:
        return return_mesh(mesh, as_tuple)

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
        return return_mesh(mesh, as_tuple)

    cap_faces = cap_loops_to_faces(
        vertices_list, plane_segments, origin, normal, tolerance=tolerance
    )
    if not cap_faces:
        return return_mesh(mesh, as_tuple)

    out_vertices = mesh.vertices
    if projected_index:
        out_vertices = np.array(vertices_list, dtype=np.float64)

    all_faces = np.vstack([mesh.faces] + [np.array(cap_faces, dtype=np.int64)]).astype(
        np.int64, copy=False
    )
    return return_mesh(ArrayMesh3(out_vertices, all_faces, mesh.edges), as_tuple)


def close_boundary(
    mesh_or_vertices: ArrayMesh3 | object,
    faces: object | None = None,
    edges: object | None = None,
    *,
    tolerance: float = 1e-9,
) -> ArrayMesh3 | tuple[NDArray[np.float64], NDArray[np.int64], NDArray[np.int64]]:
    """Close all planar boundary holes in a mesh.

    Detects boundary edges, stitches them into loops, fits a best-fit plane
    to each loop via SVD, and triangulates planar loops. Raises
    ``ValueError`` if any boundary loop is non-planar.
    """
    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive")

    mesh, as_tuple = coerce_mesh(mesh_or_vertices, faces, edges)
    boundary = boundary_edges(mesh)
    if not boundary:
        return return_mesh(mesh, as_tuple)

    vertices_np = mesh.vertices.astype(np.float64, copy=False)
    loops = stitch_segments(boundary)
    if not loops:
        return return_mesh(mesh, as_tuple)

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
        return return_mesh(mesh, as_tuple)

    all_faces = np.vstack([mesh.faces] + [np.array(all_cap_faces, dtype=np.int64)]).astype(
        np.int64, copy=False
    )
    return return_mesh(ArrayMesh3(mesh.vertices, all_faces, mesh.edges), as_tuple)


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
