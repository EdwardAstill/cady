"""Triangulation for closed 2D and planar 3D curve or edge loops."""

from __future__ import annotations

from dataclasses import dataclass
from math import acos, ceil, degrees, isfinite, sqrt
from typing import Literal, TypeAlias

import numpy as np
from numpy.typing import NDArray

from cady.operations.mesh_topology import edge_loops
from cady.utils import loop_edges

Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]
FaceIndex: TypeAlias = tuple[int, int, int]
RefinementSplit: TypeAlias = (
    tuple[Literal["edge"], tuple[int, int]] | tuple[Literal["centroid"], FaceIndex]
)
PointArray2 = NDArray[np.float64]
PointArray3 = NDArray[np.float64]
EdgeArray = NDArray[np.int64]
FaceArray = NDArray[np.int64]


@dataclass(frozen=True, slots=True)
class TriangulationGuide:
    """Optional constraints for simple boundary-guided triangulation."""

    target_edge_length: float | None = None
    max_edge_length: float | None = None
    max_area: float | None = None
    min_angle_degrees: float | None = None


@dataclass(frozen=True, slots=True)
class _LoopProjection3:
    points: PointArray2
    origin: NDArray[np.float64]
    x_axis: NDArray[np.float64]
    y_axis: NDArray[np.float64]


def triangulate_curve2(
    curve: object,
    *,
    tolerance: float,
    guide: TriangulationGuide | None = None,
):
    """Fill a closed 2D curve and return a ``Mesh2``."""
    from cady.geometry.mesh import Mesh2

    if not getattr(curve, "closed", False):
        raise ValueError("curve must be closed to triangulate")
    to_array = getattr(curve, "to_array", None)
    if not callable(to_array):
        raise TypeError("curve must provide to_array(tolerance=...)")
    nodes = _coerce_points2(to_array(tolerance=tolerance))
    boundary_edges = np.asarray(loop_edges(len(nodes)), dtype=np.int64)
    nodes_out, boundary_edges, _all_edges, faces = _triangulate_mesh2_arrays(
        nodes,
        boundary_edges,
        tolerance=tolerance,
        guide=guide,
    )
    vertices = tuple((float(x), float(y)) for x, y in nodes_out)
    edge_values = tuple((int(a), int(b)) for a, b in boundary_edges)
    face_values = tuple((int(a), int(b), int(c)) for a, b, c in faces)
    return Mesh2(vertices, face_values, edge_values)


def triangulate_curve3(
    curve: object,
    *,
    tolerance: float,
    guide: TriangulationGuide | None = None,
):
    """Fill a closed planar 3D curve and return a ``Mesh3``."""
    from cady.geometry.mesh import Mesh3

    if not getattr(curve, "closed", False):
        raise ValueError("curve must be closed to triangulate")
    to_array = getattr(curve, "to_array", None)
    if not callable(to_array):
        raise TypeError("curve must provide to_array(tolerance=...)")
    nodes = _coerce_points3(to_array(tolerance=tolerance))
    boundary_edges = np.asarray(loop_edges(len(nodes)), dtype=np.int64)
    nodes_out, boundary_edges, _all_edges, faces = _triangulate_mesh3_arrays(
        nodes,
        boundary_edges,
        tolerance=tolerance,
        guide=guide,
    )
    vertices = tuple((float(x), float(y), float(z)) for x, y, z in nodes_out)
    edge_values = tuple((int(a), int(b)) for a, b in boundary_edges)
    face_values = tuple((int(a), int(b), int(c)) for a, b, c in faces)
    return Mesh3(vertices, face_values, edge_values)


def triangulate_mesh2(
    nodes: object,
    edges: object,
    *,
    tolerance: float = 1e-9,
    guide: TriangulationGuide | None = None,
) -> tuple[PointArray2, EdgeArray, FaceArray]:
    """Triangulate closed 2D edge loops and return nodes, edges, and faces."""
    nodes_out, _boundary_edges, edges_out, faces = _triangulate_mesh2_arrays(
        _coerce_points2(nodes),
        _coerce_edges(edges),
        tolerance=tolerance,
        guide=guide,
    )
    return nodes_out, edges_out, faces


def triangulate_mesh3(
    nodes: object,
    edges: object,
    *,
    tolerance: float = 1e-9,
    guide: TriangulationGuide | None = None,
) -> tuple[PointArray3, EdgeArray, FaceArray]:
    """Project planar 3D edge loops and return nodes, edges, and faces."""
    nodes_out, _boundary_edges, edges_out, faces = _triangulate_mesh3_arrays(
        _coerce_points3(nodes),
        _coerce_edges(edges),
        tolerance=tolerance,
        guide=guide,
    )
    return nodes_out, edges_out, faces


def _triangulate_mesh2_arrays(
    nodes: PointArray2,
    edges: EdgeArray,
    *,
    tolerance: float,
    guide: TriangulationGuide | None,
) -> tuple[PointArray2, EdgeArray, EdgeArray, FaceArray]:
    guide = _validate_guide(guide)
    nodes_out, edges_out = _refine_edges2(
        nodes,
        edges,
        guide,
    )
    faces: list[FaceIndex] = []
    protected_edges = _edge_key_set(edges_out)
    for loop in edge_loops(edges_out):
        if _guide_refines_faces(guide):
            nodes_out, loop_faces = _triangulate_seeded_loop2(
                nodes_out,
                loop,
                tolerance,
            )
        else:
            loop_faces = _triangulate_loop2(nodes_out, loop, tolerance)
        nodes_out, loop_faces = _refine_triangle_mesh2(
            nodes_out,
            loop_faces,
            protected_edges=protected_edges,
            tolerance=tolerance,
            guide=guide,
        )
        faces.extend(loop_faces)
    faces_array = _face_array(faces)
    return nodes_out, edges_out, _add_internal_edges(edges_out, faces_array), faces_array


def _triangulate_mesh3_arrays(
    nodes: PointArray3,
    edges: EdgeArray,
    *,
    tolerance: float,
    guide: TriangulationGuide | None,
) -> tuple[PointArray3, EdgeArray, EdgeArray, FaceArray]:
    guide = _validate_guide(guide)
    nodes_out, edges_out = _refine_edges3(
        nodes,
        edges,
        guide,
    )
    faces: list[FaceIndex] = []
    protected_edges = _edge_key_set(edges_out)
    for loop in edge_loops(edges_out):
        projection = _project_loop3(nodes_out, loop, tolerance)
        local_loop = tuple(range(len(loop)))
        if _guide_refines_faces(guide):
            projected, local_faces = _triangulate_seeded_loop2(
                projection.points,
                local_loop,
                tolerance,
            )
            if len(projected) > len(projection.points):
                seed = projected[-1]
                seed3 = (
                    projection.origin + seed[0] * projection.x_axis + seed[1] * projection.y_axis
                )
                seed_index = len(nodes_out)
                nodes_out = np.vstack((nodes_out, seed3)).astype(np.float64)
                loop_faces = [
                    (
                        loop[a] if a < len(loop) else seed_index,
                        loop[b] if b < len(loop) else seed_index,
                        loop[c] if c < len(loop) else seed_index,
                    )
                    for a, b, c in local_faces
                ]
            else:
                loop_faces = [(loop[a], loop[b], loop[c]) for a, b, c in local_faces]
        else:
            local_faces = _triangulate_loop2(projection.points, local_loop, tolerance)
            loop_faces = [(loop[a], loop[b], loop[c]) for a, b, c in local_faces]
        nodes_out, loop_faces = _refine_triangle_mesh3(
            nodes_out,
            loop_faces,
            protected_edges=protected_edges,
            tolerance=tolerance,
            guide=guide,
        )
        faces.extend(loop_faces)
    faces_array = _face_array(faces)
    return nodes_out, edges_out, _add_internal_edges(edges_out, faces_array), faces_array


def triangulate2(
    nodes: object,
    edges: object,
    *,
    tolerance: float = 1e-9,
    guide: TriangulationGuide | None = None,
) -> tuple[PointArray2, FaceArray]:
    """Compatibility wrapper returning ``(nodes, faces)`` for 2D loops."""
    nodes_out, _edges, faces = triangulate_mesh2(
        nodes,
        edges,
        tolerance=tolerance,
        guide=guide,
    )
    return nodes_out, faces


def triangulate3(
    nodes: object,
    edges: object,
    *,
    tolerance: float = 1e-9,
    guide: TriangulationGuide | None = None,
) -> tuple[PointArray3, FaceArray]:
    """Compatibility wrapper returning ``(nodes, faces)`` for planar 3D loops."""
    nodes_out, _edges, faces = triangulate_mesh3(
        nodes,
        edges,
        tolerance=tolerance,
        guide=guide,
    )
    return nodes_out, faces


def _coerce_points2(value: object) -> PointArray2:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError("nodes must have shape (n, 2)")
    if not np.all(np.isfinite(array)):
        raise ValueError("nodes must contain only finite values")
    return np.array(array, dtype=np.float64, copy=True)


def _coerce_points3(value: object) -> PointArray3:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("nodes must have shape (n, 3)")
    if not np.all(np.isfinite(array)):
        raise ValueError("nodes must contain only finite values")
    return np.array(array, dtype=np.float64, copy=True)


def _coerce_edges(value: object) -> EdgeArray:
    array = np.asarray(value, dtype=np.int64)
    if array.size == 0:
        return np.empty((0, 2), dtype=np.int64)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError("edges must have shape (n, 2)")
    return np.array(array, dtype=np.int64, copy=True)


def _validate_guide(guide: TriangulationGuide | None) -> TriangulationGuide | None:
    if guide is None:
        return None
    for name in ("target_edge_length", "max_edge_length", "max_area"):
        value = getattr(guide, name)
        if value is not None and (not isfinite(value) or value <= 0.0):
            raise ValueError(f"{name} must be positive")
    if guide.min_angle_degrees is not None and (
        not isfinite(guide.min_angle_degrees)
        or guide.min_angle_degrees <= 0.0
        or guide.min_angle_degrees >= 60.0
    ):
        raise ValueError("min_angle_degrees must be between 0 and 60")
    return guide


def _guide_edge_length(guide: TriangulationGuide | None) -> float | None:
    if guide is None:
        return None
    values = [value for value in (guide.max_edge_length, guide.target_edge_length) if value]
    return min(values) if values else None


def _refine_edges2(
    nodes: PointArray2,
    edges: EdgeArray,
    guide: TriangulationGuide | None,
) -> tuple[PointArray2, EdgeArray]:
    return _refine_edges(nodes, edges, _guide_edge_length(guide))


def _refine_edges3(
    nodes: PointArray3,
    edges: EdgeArray,
    guide: TriangulationGuide | None,
) -> tuple[PointArray3, EdgeArray]:
    return _refine_edges(nodes, edges, _guide_edge_length(guide))


def _refine_edges(
    nodes: NDArray[np.float64],
    edges: EdgeArray,
    max_length: float | None,
) -> tuple[NDArray[np.float64], EdgeArray]:
    if max_length is None or len(edges) == 0:
        return nodes, edges

    vertices = [np.array(node, dtype=np.float64, copy=True) for node in nodes]
    refined_edges: list[tuple[int, int]] = []
    for start_raw, end_raw in edges:
        start = int(start_raw)
        end = int(end_raw)
        length = float(np.linalg.norm(nodes[end] - nodes[start]))
        segments = max(1, int(ceil(length / max_length)))
        previous = start
        for segment in range(1, segments):
            ratio = segment / segments
            point = nodes[start] + (nodes[end] - nodes[start]) * ratio
            current = len(vertices)
            vertices.append(np.array(point, dtype=np.float64, copy=True))
            refined_edges.append((previous, current))
            previous = current
        refined_edges.append((previous, end))
    return np.asarray(vertices, dtype=np.float64), np.asarray(refined_edges, dtype=np.int64)


def _face_array(faces: list[FaceIndex]) -> FaceArray:
    if not faces:
        return np.empty((0, 3), dtype=np.int64)
    return np.asarray(faces, dtype=np.int64)


def _add_internal_edges(edges: EdgeArray, faces: FaceArray) -> EdgeArray:
    edge_set = {
        (min(int(start), int(end)), max(int(start), int(end)))
        for start, end in edges
        if int(start) != int(end)
    }
    for a, b, c in faces:
        for start, end in ((int(a), int(b)), (int(b), int(c)), (int(c), int(a))):
            if start != end:
                edge_set.add((min(start, end), max(start, end)))
    if not edge_set:
        return np.empty((0, 2), dtype=np.int64)
    return np.asarray(sorted(edge_set), dtype=np.int64)


def _edge_key_set(edges: EdgeArray) -> set[tuple[int, int]]:
    return {
        (min(int(start), int(end)), max(int(start), int(end)))
        for start, end in edges
        if int(start) != int(end)
    }


def _refine_triangle_mesh2(
    nodes: PointArray2,
    faces: list[FaceIndex],
    *,
    protected_edges: set[tuple[int, int]],
    tolerance: float,
    guide: TriangulationGuide | None,
) -> tuple[PointArray2, list[FaceIndex]]:
    nodes_out, refined = _refine_triangle_mesh(
        nodes,
        faces,
        protected_edges=protected_edges,
        tolerance=tolerance,
        guide=guide,
    )
    return nodes_out, refined


def _refine_triangle_mesh3(
    nodes: PointArray3,
    faces: list[FaceIndex],
    *,
    protected_edges: set[tuple[int, int]],
    tolerance: float,
    guide: TriangulationGuide | None,
) -> tuple[PointArray3, list[FaceIndex]]:
    nodes_out, refined = _refine_triangle_mesh(
        nodes,
        faces,
        protected_edges=protected_edges,
        tolerance=tolerance,
        guide=guide,
    )
    return nodes_out, refined


def _refine_triangle_mesh(
    nodes: NDArray[np.float64],
    faces: list[FaceIndex],
    *,
    protected_edges: set[tuple[int, int]],
    tolerance: float,
    guide: TriangulationGuide | None,
) -> tuple[NDArray[np.float64], list[FaceIndex]]:
    if not _guide_refines_faces(guide) or not faces:
        return nodes, faces

    vertices = [np.array(node, dtype=np.float64, copy=True) for node in nodes]
    refined = list(faces)
    max_passes = 64
    min_area = tolerance * tolerance
    refined = _constrained_delaunay_faces(
        np.asarray(vertices, dtype=np.float64),
        refined,
        protected_edges=protected_edges,
        tolerance=tolerance,
    )

    for _ in range(max_passes):
        nodes_array = np.asarray(vertices, dtype=np.float64)
        edge_splits: dict[tuple[int, int], int] = {}
        centroid_faces: set[FaceIndex] = set()
        for face in refined:
            split = _next_refinement_split(
                nodes_array,
                [face],
                protected_edges=protected_edges,
                guide=guide,
                tolerance=tolerance,
            )
            if split is None:
                continue
            if split[0] == "edge":
                edge_splits.setdefault(split[1], -1)
            else:
                centroid_faces.add(split[1])

        if not edge_splits and not centroid_faces:
            break

        for edge in edge_splits:
            start, end = edge
            point = 0.5 * (vertices[start] + vertices[end])
            edge_splits[edge] = len(vertices)
            vertices.append(np.array(point, dtype=np.float64, copy=True))

        centroid_by_face: dict[FaceIndex, int] = {}
        for face in centroid_faces:
            point = (vertices[face[0]] + vertices[face[1]] + vertices[face[2]]) / 3.0
            centroid_by_face[face] = len(vertices)
            vertices.append(np.array(point, dtype=np.float64, copy=True))

        split_nodes = np.asarray(vertices, dtype=np.float64)
        next_faces: list[FaceIndex] = []
        for face in refined:
            selected_edges = [edge for edge in _face_edges(face) if edge in edge_splits]
            if selected_edges:
                children = [face]
                for edge in selected_edges:
                    children = _split_faces_on_edge(
                        children,
                        edge,
                        edge_splits[edge],
                        split_nodes,
                        min_area=min_area,
                    )
                next_faces.extend(children)
                continue

            centroid = centroid_by_face.get(face)
            if centroid is not None:
                next_faces.extend(
                    _split_face_at_point(
                        [face],
                        face,
                        centroid,
                        split_nodes,
                        min_area=min_area,
                    )
                )
                continue

            next_faces.append(face)

        refined = next_faces
        refined = _constrained_delaunay_faces(
            np.asarray(vertices, dtype=np.float64),
            refined,
            protected_edges=protected_edges,
            tolerance=tolerance,
        )

    return np.asarray(vertices, dtype=np.float64), refined


def _constrained_delaunay_faces(
    nodes: NDArray[np.float64],
    faces: list[FaceIndex],
    *,
    protected_edges: set[tuple[int, int]],
    tolerance: float,
) -> list[FaceIndex]:
    if len(faces) < 2:
        return faces

    projected = _project_nodes_for_delaunay(nodes, faces)
    refined = list(faces)
    max_iterations = max(1, len(refined) * len(refined))
    for _ in range(max_iterations):
        edge_faces = _interior_edge_faces(refined, protected_edges)
        flipped = False
        for edge, adjacent in edge_faces.items():
            if len(adjacent) != 2:
                continue

            left_index, right_index = adjacent
            left = refined[left_index]
            right = refined[right_index]
            a, b = edge
            c = _opposite_vertex(left, edge)
            d = _opposite_vertex(right, edge)
            if c is None or d is None or c == d:
                continue
            if not _is_convex_quad2(projected, a, b, c, d, tolerance):
                continue
            if not _point_in_circumcircle2(
                projected[a],
                projected[b],
                projected[c],
                projected[d],
                tolerance,
            ):
                continue

            first = _ccw_face2(projected, (c, d, a))
            second = _ccw_face2(projected, (d, c, b))
            if _triangle_area(projected, first) <= tolerance * tolerance:
                continue
            if _triangle_area(projected, second) <= tolerance * tolerance:
                continue
            refined[left_index] = first
            refined[right_index] = second
            flipped = True
            break

        if not flipped:
            break

    return refined


def _project_nodes_for_delaunay(
    nodes: NDArray[np.float64],
    faces: list[FaceIndex],
) -> PointArray2:
    if nodes.shape[1] == 2:
        return nodes
    used = sorted({index for face in faces for index in face})
    points = nodes[used]
    origin = points.mean(axis=0)
    centered = points - origin
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    normal = vt[-1]
    reference = (
        np.array([1.0, 0.0, 0.0], dtype=np.float64)
        if abs(float(normal[0])) < 0.9
        else np.array([0.0, 1.0, 0.0], dtype=np.float64)
    )
    x_axis = np.cross(normal, reference)
    x_axis = x_axis / np.linalg.norm(x_axis)
    y_axis = np.cross(normal, x_axis)
    projected = np.zeros((len(nodes), 2), dtype=np.float64)
    projected[:, 0] = (nodes - origin) @ x_axis
    projected[:, 1] = (nodes - origin) @ y_axis
    return projected


def _interior_edge_faces(
    faces: list[FaceIndex],
    protected_edges: set[tuple[int, int]],
) -> dict[tuple[int, int], list[int]]:
    edge_faces: dict[tuple[int, int], list[int]] = {}
    for index, face in enumerate(faces):
        for edge in _face_edges(face):
            if edge in protected_edges:
                continue
            edge_faces.setdefault(edge, []).append(index)
    return edge_faces


def _opposite_vertex(face: FaceIndex, edge: tuple[int, int]) -> int | None:
    a, b = edge
    for index in face:
        if index != a and index != b:
            return index
    return None


def _is_convex_quad2(
    nodes: PointArray2,
    a: int,
    b: int,
    c: int,
    d: int,
    tolerance: float,
) -> bool:
    edge_side_c = _cross2(nodes[a], nodes[b], nodes[c])
    edge_side_d = _cross2(nodes[a], nodes[b], nodes[d])
    new_edge_side_a = _cross2(nodes[c], nodes[d], nodes[a])
    new_edge_side_b = _cross2(nodes[c], nodes[d], nodes[b])
    return edge_side_c * edge_side_d < -(
        tolerance * tolerance
    ) and new_edge_side_a * new_edge_side_b < -(tolerance * tolerance)


def _point_in_circumcircle2(
    a: NDArray[np.float64],
    b: NDArray[np.float64],
    c: NDArray[np.float64],
    point: NDArray[np.float64],
    tolerance: float,
) -> bool:
    ax = float(a[0] - point[0])
    ay = float(a[1] - point[1])
    bx = float(b[0] - point[0])
    by = float(b[1] - point[1])
    cx = float(c[0] - point[0])
    cy = float(c[1] - point[1])
    determinant = (
        (ax * ax + ay * ay) * (bx * cy - cx * by)
        - (bx * bx + by * by) * (ax * cy - cx * ay)
        + (cx * cx + cy * cy) * (ax * by - bx * ay)
    )
    orientation = _cross2(a, b, c)
    if orientation < 0.0:
        determinant = -determinant
    return determinant > tolerance * tolerance


def _ccw_face2(nodes: PointArray2, face: FaceIndex) -> FaceIndex:
    a, b, c = face
    if _cross2(nodes[a], nodes[b], nodes[c]) < 0.0:
        return (a, c, b)
    return face


def _guide_refines_faces(guide: TriangulationGuide | None) -> bool:
    return guide is not None and (
        _guide_edge_length(guide) is not None
        or guide.max_area is not None
        or guide.min_angle_degrees is not None
    )


def _next_refinement_split(
    nodes: NDArray[np.float64],
    faces: list[FaceIndex],
    *,
    protected_edges: set[tuple[int, int]],
    guide: TriangulationGuide | None,
    tolerance: float,
) -> RefinementSplit | None:
    edge_limit = _guide_edge_length(guide)
    area_limit = None if guide is None else guide.max_area
    angle_limit = None if guide is None else guide.min_angle_degrees
    best_score = 1.0
    best_face: FaceIndex | None = None
    best_edge: tuple[int, int] | None = None

    for face in faces:
        lengths = _face_edge_lengths(nodes, face)
        area = _triangle_area(nodes, face)
        if area <= tolerance * tolerance:
            continue

        min_angle = _min_angle_degrees(lengths)
        score = 1.0
        if edge_limit is not None:
            score = max(score, max(lengths) / edge_limit)
        if area_limit is not None:
            score = max(score, sqrt(area / area_limit))
        if angle_limit is not None and min_angle > 0.0:
            score = max(score, angle_limit / min_angle)
        if score <= best_score + 1e-12:
            continue

        edges = _face_edges(face)
        candidate_edges = [
            edge
            for _length, edge in sorted(
                zip(lengths, edges, strict=True),
                reverse=True,
            )
            if edge not in protected_edges
        ]
        best_score = score
        best_face = face
        best_edge = candidate_edges[0] if candidate_edges else None

    if best_face is None:
        return None
    if best_edge is not None:
        return ("edge", best_edge)
    return ("centroid", best_face)


def _split_faces_on_edge(
    faces: list[FaceIndex],
    edge: tuple[int, int],
    midpoint: int,
    nodes: NDArray[np.float64],
    *,
    min_area: float,
) -> list[FaceIndex]:
    refined: list[FaceIndex] = []
    edge_key = (min(edge), max(edge))
    for face in faces:
        if edge_key not in _face_edges(face):
            refined.append(face)
            continue
        for child in _split_face_on_edge(face, edge_key, midpoint):
            if _triangle_area(nodes, child) > min_area:
                refined.append(child)
    return refined


def _split_face_on_edge(
    face: FaceIndex,
    edge: tuple[int, int],
    midpoint: int,
) -> tuple[FaceIndex, FaceIndex]:
    for position in range(3):
        start = face[position]
        end = face[(position + 1) % 3]
        other = face[(position + 2) % 3]
        if (min(start, end), max(start, end)) == edge:
            return (start, midpoint, other), (midpoint, end, other)
    raise ValueError("face does not contain split edge")


def _split_face_at_point(
    faces: list[FaceIndex],
    face: FaceIndex,
    point: int,
    nodes: NDArray[np.float64],
    *,
    min_area: float,
) -> list[FaceIndex]:
    refined: list[FaceIndex] = []
    for candidate in faces:
        if candidate != face:
            refined.append(candidate)
            continue
        a, b, c = candidate
        for child in ((a, b, point), (b, c, point), (c, a, point)):
            if _triangle_area(nodes, child) > min_area:
                refined.append(child)
    return refined


def _face_edges(face: FaceIndex) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    a, b, c = face
    return (
        (min(a, b), max(a, b)),
        (min(b, c), max(b, c)),
        (min(c, a), max(c, a)),
    )


def _face_edge_lengths(nodes: NDArray[np.float64], face: FaceIndex) -> tuple[float, float, float]:
    a, b, c = face
    return (
        float(np.linalg.norm(nodes[a] - nodes[b])),
        float(np.linalg.norm(nodes[b] - nodes[c])),
        float(np.linalg.norm(nodes[c] - nodes[a])),
    )


def _triangle_area(nodes: NDArray[np.float64], face: FaceIndex) -> float:
    a, b, c = face
    ab = nodes[b] - nodes[a]
    ac = nodes[c] - nodes[a]
    if nodes.shape[1] == 2:
        return 0.5 * abs(float(ab[0] * ac[1] - ab[1] * ac[0]))
    return 0.5 * float(np.linalg.norm(np.cross(ab, ac)))


def _min_angle_degrees(lengths: tuple[float, float, float]) -> float:
    ab, bc, ca = lengths
    if ab <= 0.0 or bc <= 0.0 or ca <= 0.0:
        return 0.0
    return min(
        _angle_degrees(ab, ca, bc),
        _angle_degrees(ab, bc, ca),
        _angle_degrees(bc, ca, ab),
    )


def _angle_degrees(first: float, second: float, opposite: float) -> float:
    denominator = 2.0 * first * second
    if denominator <= 0.0:
        return 0.0
    cosine = (first * first + second * second - opposite * opposite) / denominator
    cosine = max(-1.0, min(1.0, cosine))
    return degrees(acos(cosine))


def _triangulate_seeded_loop2(
    nodes: PointArray2,
    loop: tuple[int, ...],
    tolerance: float,
) -> tuple[PointArray2, list[FaceIndex]]:
    indices = list(loop)
    if len(indices) < 3:
        return nodes, []
    if _signed_area2(nodes, indices) < 0.0:
        indices.reverse()

    seed = _interior_seed2(nodes, indices, tolerance)
    if seed is None or not _seed_sees_loop2(nodes, indices, seed, tolerance):
        return nodes, _triangulate_loop2(nodes, tuple(indices), tolerance)

    seed_index = len(nodes)
    seeded_nodes = np.vstack((nodes, seed)).astype(np.float64)
    faces: list[FaceIndex] = []
    for start, end in zip(indices, indices[1:] + indices[:1], strict=True):
        face = (start, end, seed_index)
        if _triangle_area(seeded_nodes, face) > tolerance * tolerance:
            faces.append(face)
    if not faces:
        return nodes, _triangulate_loop2(nodes, tuple(indices), tolerance)
    return seeded_nodes, faces


def _interior_seed2(
    nodes: PointArray2,
    indices: list[int],
    tolerance: float,
) -> NDArray[np.float64] | None:
    polygon = [nodes[index] for index in indices]
    lower = np.min(np.asarray(polygon, dtype=np.float64), axis=0)
    upper = np.max(np.asarray(polygon, dtype=np.float64), axis=0)
    span = upper - lower

    candidates = [
        _polygon_centroid2(nodes, indices),
        np.mean(np.asarray(polygon, dtype=np.float64), axis=0),
        (lower + upper) / 2.0,
    ]
    for x_step in range(1, 6):
        for y_step in range(1, 6):
            candidates.append(
                np.array(
                    (
                        lower[0] + span[0] * x_step / 6.0,
                        lower[1] + span[1] * y_step / 6.0,
                    ),
                    dtype=np.float64,
                )
            )

    best: NDArray[np.float64] | None = None
    best_distance = tolerance
    centre = (lower + upper) / 2.0
    best_centre_distance = float("inf")
    for candidate in candidates:
        if not _point_in_loop2(candidate, nodes, indices, tolerance):
            continue
        boundary_distance = _distance_to_loop2(candidate, nodes, indices)
        centre_distance = float(np.linalg.norm(candidate - centre))
        if (
            boundary_distance > best_distance
            or abs(boundary_distance - best_distance) <= tolerance
            and centre_distance < best_centre_distance
        ):
            best = candidate
            best_distance = boundary_distance
            best_centre_distance = centre_distance
    return best


def _polygon_centroid2(nodes: PointArray2, indices: list[int]) -> NDArray[np.float64]:
    area_sum = 0.0
    x_sum = 0.0
    y_sum = 0.0
    for start, end in zip(indices, indices[1:] + indices[:1], strict=True):
        cross = float(nodes[start, 0] * nodes[end, 1] - nodes[end, 0] * nodes[start, 1])
        area_sum += cross
        x_sum += float(nodes[start, 0] + nodes[end, 0]) * cross
        y_sum += float(nodes[start, 1] + nodes[end, 1]) * cross
    if abs(area_sum) <= 1e-18:
        return np.mean(nodes[indices], axis=0)
    return np.array((x_sum / (3.0 * area_sum), y_sum / (3.0 * area_sum)), dtype=np.float64)


def _seed_sees_loop2(
    nodes: PointArray2,
    indices: list[int],
    seed: NDArray[np.float64],
    tolerance: float,
) -> bool:
    for vertex_position, vertex in enumerate(indices):
        if not _segment_stays_in_loop2(
            seed,
            nodes[vertex],
            vertex_position,
            nodes,
            indices,
            tolerance,
        ):
            return False
    return True


def _segment_stays_in_loop2(
    start: NDArray[np.float64],
    end: NDArray[np.float64],
    end_position: int,
    nodes: PointArray2,
    indices: list[int],
    tolerance: float,
) -> bool:
    for fraction in (0.25, 0.5, 0.75):
        point = start + (end - start) * fraction
        if not _point_in_loop2(point, nodes, indices, tolerance):
            return False

    end_vertex = indices[end_position]
    adjacent = {end_vertex, indices[end_position - 1], indices[(end_position + 1) % len(indices)]}
    for edge_start, edge_end in zip(indices, indices[1:] + indices[:1], strict=True):
        if edge_start in adjacent and edge_end in adjacent:
            continue
        if _segments_intersect2(start, end, nodes[edge_start], nodes[edge_end], tolerance):
            return False
    return True


def _point_in_loop2(
    point: NDArray[np.float64],
    nodes: PointArray2,
    indices: list[int],
    tolerance: float,
) -> bool:
    inside = False
    previous = indices[-1]
    for current in indices:
        a = nodes[current]
        b = nodes[previous]
        if _point_on_segment2(point, a, b, tolerance):
            return False
        if ((a[1] > point[1]) != (b[1] > point[1])) and (
            point[0] < (b[0] - a[0]) * (point[1] - a[1]) / (b[1] - a[1]) + a[0]
        ):
            inside = not inside
        previous = current
    return inside


def _distance_to_loop2(
    point: NDArray[np.float64],
    nodes: PointArray2,
    indices: list[int],
) -> float:
    return min(
        _distance_to_segment2(point, nodes[start], nodes[end])
        for start, end in zip(indices, indices[1:] + indices[:1], strict=True)
    )


def _distance_to_segment2(
    point: NDArray[np.float64],
    start: NDArray[np.float64],
    end: NDArray[np.float64],
) -> float:
    segment = end - start
    length_squared = float(np.dot(segment, segment))
    if length_squared == 0.0:
        return float(np.linalg.norm(point - start))
    ratio = max(0.0, min(1.0, float(np.dot(point - start, segment)) / length_squared))
    closest = start + segment * ratio
    return float(np.linalg.norm(point - closest))


def _point_on_segment2(
    point: NDArray[np.float64],
    start: NDArray[np.float64],
    end: NDArray[np.float64],
    tolerance: float,
) -> bool:
    return (
        abs(_cross2(start, end, point)) <= tolerance
        and min(start[0], end[0]) - tolerance <= point[0] <= max(start[0], end[0]) + tolerance
        and min(start[1], end[1]) - tolerance <= point[1] <= max(start[1], end[1]) + tolerance
    )


def _segments_intersect2(
    a: NDArray[np.float64],
    b: NDArray[np.float64],
    c: NDArray[np.float64],
    d: NDArray[np.float64],
    tolerance: float,
) -> bool:
    ab_c = _cross2(a, b, c)
    ab_d = _cross2(a, b, d)
    cd_a = _cross2(c, d, a)
    cd_b = _cross2(c, d, b)
    if ((ab_c > tolerance and ab_d < -tolerance) or (ab_c < -tolerance and ab_d > tolerance)) and (
        (cd_a > tolerance and cd_b < -tolerance) or (cd_a < -tolerance and cd_b > tolerance)
    ):
        return True
    return (
        abs(ab_c) <= tolerance
        and _point_on_segment2(c, a, b, tolerance)
        or abs(ab_d) <= tolerance
        and _point_on_segment2(d, a, b, tolerance)
        or abs(cd_a) <= tolerance
        and _point_on_segment2(a, c, d, tolerance)
        or abs(cd_b) <= tolerance
        and _point_on_segment2(b, c, d, tolerance)
    )


def _triangulate_loop2(
    nodes: PointArray2,
    loop: tuple[int, ...],
    tolerance: float,
) -> list[FaceIndex]:
    indices = list(loop)
    if len(indices) < 3:
        return []
    if _signed_area2(nodes, indices) < 0.0:
        indices.reverse()

    faces: list[FaceIndex] = []
    guard = len(indices) * len(indices)
    while len(indices) > 3 and guard > 0:
        guard -= 1
        clipped = False
        for position, current in enumerate(indices):
            previous = indices[position - 1]
            following = indices[(position + 1) % len(indices)]
            if _cross2(nodes[previous], nodes[current], nodes[following]) <= tolerance:
                continue
            if any(
                candidate not in {previous, current, following}
                and _point_in_triangle(
                    nodes[candidate],
                    nodes[previous],
                    nodes[current],
                    nodes[following],
                    tolerance,
                )
                for candidate in indices
            ):
                continue
            faces.append((previous, current, following))
            del indices[position]
            clipped = True
            break
        if clipped:
            continue

        for position, current in enumerate(indices):
            previous = indices[position - 1]
            following = indices[(position + 1) % len(indices)]
            if abs(_cross2(nodes[previous], nodes[current], nodes[following])) <= tolerance:
                del indices[position]
                clipped = True
                break
        if not clipped:
            break

    if len(indices) == 3 and abs(_cross2(nodes[indices[0]], nodes[indices[1]], nodes[indices[2]])):
        faces.append((indices[0], indices[1], indices[2]))
    return faces


def _project_loop3(
    nodes: PointArray3,
    loop: tuple[int, ...],
    tolerance: float,
) -> _LoopProjection3:
    points = nodes[list(loop)]
    origin = points.mean(axis=0)
    centered = points - origin
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    normal = vt[-1]
    deviations = np.abs(centered @ normal)
    if len(deviations) and float(np.max(deviations)) > tolerance:
        raise ValueError(
            "3D edge loop is non-planar "
            f"(max deviation {float(np.max(deviations)):.3e} > tolerance {tolerance:.3e})"
        )
    reference = (
        np.array([1.0, 0.0, 0.0], dtype=np.float64)
        if abs(float(normal[0])) < 0.9
        else np.array([0.0, 1.0, 0.0], dtype=np.float64)
    )
    x_axis = np.cross(normal, reference)
    x_axis = x_axis / np.linalg.norm(x_axis)
    y_axis = np.cross(normal, x_axis)
    return _LoopProjection3(
        np.column_stack((centered @ x_axis, centered @ y_axis)).astype(np.float64),
        origin,
        x_axis,
        y_axis,
    )


def _signed_area2(nodes: PointArray2, indices: list[int]) -> float:
    return 0.5 * sum(
        float(nodes[start, 0] * nodes[end, 1] - nodes[end, 0] * nodes[start, 1])
        for start, end in zip(indices, indices[1:] + indices[:1], strict=True)
    )


def _cross2(a: NDArray[np.float64], b: NDArray[np.float64], c: NDArray[np.float64]) -> float:
    return float((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))


def _point_in_triangle(
    point: NDArray[np.float64],
    a: NDArray[np.float64],
    b: NDArray[np.float64],
    c: NDArray[np.float64],
    tolerance: float,
) -> bool:
    return (
        _cross2(a, b, point) >= -tolerance
        and _cross2(b, c, point) >= -tolerance
        and _cross2(c, a, point) >= -tolerance
    )


__all__ = [
    "TriangulationGuide",
    "triangulate2",
    "triangulate3",
    "triangulate_curve2",
    "triangulate_curve3",
    "triangulate_mesh2",
    "triangulate_mesh3",
]
