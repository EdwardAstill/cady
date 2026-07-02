"""Compare cady polygon triangulation at different mesh sizes.

Run from the repository root:

    PYTHONPATH=src .venv/bin/python examples/scripts/triangulate_polygon_resolutions.py
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from math import acos, ceil, degrees, isfinite, radians, sqrt, tan
from typing import Literal, TypeAlias

import numpy as np
from numpy.typing import NDArray

from cady import Camera, DisplayStyle, Mesh3, Polyline3, Scene

Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]
EdgeIndex: TypeAlias = tuple[int, int]
FaceIndex: TypeAlias = tuple[int, int, int]
RefinementSplit: TypeAlias = (
    tuple[Literal["edge"], tuple[int, int]] | tuple[Literal["centroid"], FaceIndex]
)
PointArray2 = NDArray[np.float64]
PointArray3 = NDArray[np.float64]
EdgeArray = NDArray[np.int64]
FaceArray = NDArray[np.int64]
ResolutionSpec: TypeAlias = float | Literal["auto"] | None
MinAngleSpec: TypeAlias = float | None
PointRows3: TypeAlias = Sequence[Point3] | NDArray[np.float64]
EdgeRows: TypeAlias = Sequence[EdgeIndex] | NDArray[np.int64]


# Local topology helpers copied into the example so it does not import operations.
def loop_edges(count: int) -> tuple[EdgeIndex, ...]:
    return tuple((index, (index + 1) % count) for index in range(count))


def stitch_segments(segments: Iterable[EdgeIndex]) -> list[list[int]]:
    neighbours: dict[int, set[int]] = defaultdict(set)
    unused_edges: set[EdgeIndex] = set()
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


def edge_loops(edges: EdgeRows) -> tuple[tuple[int, ...], ...]:
    edges_array = np.asarray(edges, dtype=np.int64)
    if edges_array.size == 0:
        return ()
    if edges_array.ndim != 2 or edges_array.shape[1] != 2:
        raise ValueError("edges must have shape (n, 2)")
    return tuple(tuple(loop) for loop in stitch_segments((int(a), int(b)) for a, b in edges_array))


# Local triangulation core copied into this example.
@dataclass(frozen=True, slots=True)
class TriangulationGuide:
    """Optional sizing constraints and output quality requirements."""

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


def triangulate_mesh3(
    nodes: PointRows3,
    edges: EdgeRows,
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
            local_faces = _constrained_delaunay_faces(
                projection.points,
                local_faces,
                protected_edges=_edge_key_set(
                    np.asarray(tuple(loop_edges(len(loop))), dtype=np.int64)
                ),
                tolerance=tolerance,
            )
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


def _coerce_points3(value: PointRows3) -> PointArray3:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("nodes must have shape (n, 3)")
    if not np.all(np.isfinite(array)):
        raise ValueError("nodes must contain only finite values")
    return np.array(array, dtype=np.float64, copy=True)


def _coerce_edges(value: EdgeRows) -> EdgeArray:
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
        _validate_min_triangle_angle(nodes, faces, guide=guide, tolerance=tolerance)
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

    nodes_out = np.asarray(vertices, dtype=np.float64)
    _validate_min_triangle_angle(nodes_out, refined, guide=guide, tolerance=tolerance)
    return nodes_out, refined


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


def _validate_min_triangle_angle(
    nodes: NDArray[np.float64],
    faces: list[FaceIndex],
    *,
    guide: TriangulationGuide | None,
    tolerance: float,
) -> None:
    if guide is None or guide.min_angle_degrees is None:
        return

    limit = guide.min_angle_degrees
    min_area = tolerance * tolerance
    worst_angle: float | None = None
    for face in faces:
        if _triangle_area(nodes, face) <= min_area:
            continue
        angle = _min_angle_degrees(_face_edge_lengths(nodes, face))
        if angle + 1e-9 >= limit:
            continue
        worst_angle = angle if worst_angle is None else min(worst_angle, angle)

    if worst_angle is not None:
        raise ValueError(
            "triangulation produced a triangle angle "
            f"{worst_angle:.6g} below min_angle_degrees {limit:.6g}"
        )


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


# Example configuration and public helpers.
TOLERANCE = 1e-6
MAX_EDGE_LENGTHS: tuple[ResolutionSpec, ...] = (None, "auto", 0.75, 0.35, 0.18)
MIN_ANGLE_DEGREES: tuple[MinAngleSpec, ...] = (None, 5.0, 10.0, 15.0)
POLYGON_POINTS: tuple[Point3, ...] = (
    (-1.65, -0.25, 0.0),
    (-1.05, -0.9, 0.0),
    (-0.2, -0.82, 0.0),
    (0.35, -1.18, 0.0),
    (1.35, -0.6, 0.0),
    (1.7, 0.18, 0.0),
    (0.85, 0.5, 0.0),
    (0.55, 1.1, 0.0),
    (-0.28, 0.68, 0.0),
    (-1.18, 0.96, 0.0),
    (-1.58, 0.35, 0.0),
)
NARROW_CHANNEL_POINTS: tuple[Point3, ...] = (
    (-2.0, -1.0, 0.0),
    (2.0, -1.0, 0.0),
    (2.0, -0.55, 0.0),
    (-1.15, -0.55, 0.0),
    (-1.15, 0.55, 0.0),
    (2.0, 0.55, 0.0),
    (2.0, 1.0, 0.0),
    (-2.0, 1.0, 0.0),
)
COMB_POINTS: tuple[Point3, ...] = (
    (-2.0, -1.0, 0.0),
    (2.0, -1.0, 0.0),
    (2.0, 1.0, 0.0),
    (1.65, 1.0, 0.0),
    (1.65, 0.15, 0.0),
    (1.25, 0.15, 0.0),
    (1.25, 1.0, 0.0),
    (0.85, 1.0, 0.0),
    (0.85, 0.15, 0.0),
    (0.45, 0.15, 0.0),
    (0.45, 1.0, 0.0),
    (0.05, 1.0, 0.0),
    (0.05, 0.15, 0.0),
    (-0.35, 0.15, 0.0),
    (-0.35, 1.0, 0.0),
    (-0.75, 1.0, 0.0),
    (-0.75, 0.15, 0.0),
    (-1.15, 0.15, 0.0),
    (-1.15, 1.0, 0.0),
    (-2.0, 1.0, 0.0),
)
THIN_NECK_POINTS: tuple[Point3, ...] = (
    (-2.0, -0.9, 0.0),
    (-0.8, -0.9, 0.0),
    (-0.45, -0.25, 0.0),
    (0.45, -0.25, 0.0),
    (0.8, -0.9, 0.0),
    (2.0, -0.9, 0.0),
    (2.0, 0.9, 0.0),
    (0.8, 0.9, 0.0),
    (0.45, 0.25, 0.0),
    (-0.45, 0.25, 0.0),
    (-0.8, 0.9, 0.0),
    (-2.0, 0.9, 0.0),
)
CRESCENT_POINTS: tuple[Point3, ...] = (
    (0.9, -1.15, 0.0),
    (0.15, -1.45, 0.0),
    (-0.75, -1.25, 0.0),
    (-1.35, -0.7, 0.0),
    (-1.55, 0.0, 0.0),
    (-1.35, 0.7, 0.0),
    (-0.75, 1.25, 0.0),
    (0.15, 1.45, 0.0),
    (0.9, 1.15, 0.0),
    (0.45, 0.72, 0.0),
    (0.18, 0.25, 0.0),
    (0.1, -0.25, 0.0),
    (0.35, -0.78, 0.0),
)
LONG_SLIVER_POINTS: tuple[Point3, ...] = (
    (-2.2, -0.04, 0.0),
    (2.2, -0.04, 0.0),
    (2.2, 0.04, 0.0),
    (-2.2, 0.04, 0.0),
)
TAPERED_NEEDLE_POINTS: tuple[Point3, ...] = (
    (-2.2, -0.18, 0.0),
    (1.95, -0.08, 0.0),
    (2.12, -0.02, 0.0),
    (2.12, 0.02, 0.0),
    (1.95, 0.08, 0.0),
    (-2.2, 0.18, 0.0),
)
HAIRLINE_SLOT_POINTS: tuple[Point3, ...] = (
    (-2.2, -0.28, 0.0),
    (2.2, -0.28, 0.0),
    (2.2, -0.18, 0.0),
    (-1.85, -0.18, 0.0),
    (-1.85, -0.14, 0.0),
    (2.2, -0.14, 0.0),
    (2.2, 0.28, 0.0),
    (-2.2, 0.28, 0.0),
)
JAGGED_BAY_POINTS: tuple[Point3, ...] = (
    (-2.0, -0.8, 0.0),
    (-1.6, -1.1, 0.0),
    (-1.1, -0.82, 0.0),
    (-0.65, -1.18, 0.0),
    (-0.2, -0.82, 0.0),
    (0.25, -1.12, 0.0),
    (0.8, -0.78, 0.0),
    (1.4, -1.0, 0.0),
    (1.9, -0.45, 0.0),
    (1.55, 0.05, 0.0),
    (1.9, 0.55, 0.0),
    (1.25, 0.9, 0.0),
    (0.75, 0.55, 0.0),
    (0.35, 1.12, 0.0),
    (-0.1, 0.58, 0.0),
    (-0.55, 1.0, 0.0),
    (-1.0, 0.48, 0.0),
    (-1.55, 0.85, 0.0),
    (-1.9, 0.2, 0.0),
    (-1.45, -0.2, 0.0),
)
POLYGON_CASES: tuple[tuple[str, tuple[Point3, ...]], ...] = (
    ("coastal concave", POLYGON_POINTS),
    ("narrow channel", NARROW_CHANNEL_POINTS),
    ("comb teeth", COMB_POINTS),
    ("thin neck", THIN_NECK_POINTS),
    ("crescent moon", CRESCENT_POINTS),
    ("long sliver", LONG_SLIVER_POINTS),
    ("tapered needle", TAPERED_NEEDLE_POINTS),
    ("hairline slot", HAIRLINE_SLOT_POINTS),
    ("jagged bay", JAGGED_BAY_POINTS),
)

MESH_STYLES = (
    DisplayStyle(color=(0.52, 0.64, 0.74), opacity=0.82),
    DisplayStyle(color=(0.35, 0.66, 0.58), opacity=0.82),
    DisplayStyle(color=(0.84, 0.57, 0.34), opacity=0.82),
    DisplayStyle(color=(0.73, 0.48, 0.70), opacity=0.82),
    DisplayStyle(color=(0.62, 0.58, 0.36), opacity=0.82),
)
HEURISTIC_STYLE = DisplayStyle(color=(0.35, 0.66, 0.58), opacity=0.82)
INPUT_POLYGON_STYLE = DisplayStyle(color=(0.05, 0.18, 0.32), render_mode="wireframe")


def example_polyline() -> Polyline3:
    return Polyline3(POLYGON_POINTS, closed=True)


def polygon_mesh_from_points(points: Sequence[Point3]) -> Mesh3:
    vertices = tuple((float(x), float(y), float(z)) for x, y, z in points)
    face = tuple(range(len(vertices)))
    return Mesh3(vertices, (face,), _polygon_face_edges((face,)))


def polygon_mesh_from_polyline(polyline: Polyline3, *, tolerance: float = TOLERANCE) -> Mesh3:
    return polygon_mesh_from_points(
        tuple((float(x), float(y), float(z)) for x, y, z in polyline.to_array(tolerance=tolerance))
    )


def triangulate3d(
    mesh: Mesh3,
    *,
    tolerance: float = TOLERANCE,
    guide: TriangulationGuide | Literal["auto"] | None = None,
    min_angle_degrees: float | None = None,
) -> Mesh3:
    if not isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("tolerance must be positive")
    if min_angle_degrees is not None and (
        not isfinite(min_angle_degrees) or min_angle_degrees <= 0.0
    ):
        raise ValueError("min_angle_degrees must be positive")
    if not mesh.faces:
        return Mesh3(mesh.vertices, (), mesh.edges)

    vertices_out: list[Point3] = []
    faces_out: list[FaceIndex] = []
    edges_out: set[EdgeIndex] = set()
    for face in mesh.faces:
        face_vertices = tuple(mesh.vertices[index] for index in face)
        local_guide = (
            _automatic_guide(
                face_vertices,
                tolerance=tolerance,
                min_angle_degrees=min_angle_degrees,
            )
            if guide == "auto"
            else guide
        )
        local_guide = _guide_with_min_angle(local_guide, min_angle_degrees)
        nodes, edges, faces = triangulate_mesh3(
            face_vertices,
            loop_edges(len(face_vertices)),
            tolerance=tolerance,
            guide=local_guide,
        )
        offset = len(vertices_out)
        vertices_out.extend((float(x), float(y), float(z)) for x, y, z in nodes)
        faces_out.extend((int(a) + offset, int(b) + offset, int(c) + offset) for a, b, c in faces)
        edges_out.update(
            (min(int(a) + offset, int(b) + offset), max(int(a) + offset, int(b) + offset))
            for a, b in edges
        )
    return Mesh3(tuple(vertices_out), tuple(faces_out), tuple(sorted(edges_out)))


def triangulate_polygon(
    polyline: Polyline3,
    *,
    max_edge_length: ResolutionSpec = None,
    tolerance: float = TOLERANCE,
) -> Mesh3:
    if max_edge_length is not None and max_edge_length != "auto" and (
        not isfinite(max_edge_length) or max_edge_length <= 0.0
    ):
        raise ValueError("max_edge_length must be positive")

    guide = (
        "auto"
        if max_edge_length == "auto"
        else None
        if max_edge_length is None
        else TriangulationGuide(max_edge_length=max_edge_length)
    )
    return triangulate3d(
        polygon_mesh_from_polyline(polyline, tolerance=tolerance),
        tolerance=tolerance,
        guide=guide,
    )


def triangulate_polygon_heuristic(
    polygon: Mesh3,
    *,
    tolerance: float = TOLERANCE,
) -> Mesh3:
    return triangulate3d(polygon, tolerance=tolerance, guide="auto")


def triangulate_resolutions(
    polyline: Polyline3,
    *,
    max_edge_lengths: Iterable[ResolutionSpec] = MAX_EDGE_LENGTHS,
    tolerance: float = TOLERANCE,
) -> tuple[tuple[ResolutionSpec, Mesh3], ...]:
    return tuple(
        (
            max_edge_length,
            triangulate_polygon(
                polyline,
                max_edge_length=max_edge_length,
                tolerance=tolerance,
            ),
        )
        for max_edge_length in max_edge_lengths
    )


def triangulate_shape_cases(
    cases: Iterable[tuple[str, Sequence[Point3]]] = POLYGON_CASES,
    *,
    tolerance: float = TOLERANCE,
) -> tuple[tuple[str, Mesh3, Mesh3], ...]:
    return tuple(
        (
            name,
            polygon,
            triangulate3d(polygon, tolerance=tolerance, guide="auto"),
        )
        for name, points in cases
        for polygon in (polygon_mesh_from_points(points),)
    )


def triangulate_min_angle_cases(
    points: Sequence[Point3] = HAIRLINE_SLOT_POINTS,
    *,
    min_angle_degrees: Iterable[MinAngleSpec] = MIN_ANGLE_DEGREES,
    tolerance: float = TOLERANCE,
) -> tuple[tuple[MinAngleSpec, Mesh3, Mesh3], ...]:
    polygon = polygon_mesh_from_points(points)
    return tuple(
        (
            angle,
            polygon,
            triangulate3d(
                polygon,
                tolerance=tolerance,
                guide="auto",
                min_angle_degrees=angle,
            ),
        )
        for angle in min_angle_degrees
    )


def build_scene(cases: tuple[tuple[ResolutionSpec, Mesh3], ...]) -> Scene:
    spacing = 4.25
    centre = (len(cases) - 1) / 2.0
    scene = Scene(
        "polygon_triangulation_sizes",
        camera=Camera.orthographic(
            position=(0.0, 0.0, 11.0),
            target=(0.0, 0.0, 0.0),
            up=(0.0, 1.0, 0.0),
            scale=10.5,
        ),
    )
    for index, (max_edge_length, mesh) in enumerate(cases):
        offset = (index - centre) * spacing
        scene = scene.add(
            _translated_mesh(mesh, offset, 0.0, 0.0),
            name=_case_name(max_edge_length),
            style=MESH_STYLES[index % len(MESH_STYLES)],
        )
    return scene


def build_min_angle_scene(cases: tuple[tuple[MinAngleSpec, Mesh3, Mesh3], ...]) -> Scene:
    spacing = 5.0
    centre = (len(cases) - 1) / 2.0
    scene = Scene(
        "polygon_triangulation_min_angles",
        camera=Camera.orthographic(
            position=(0.0, 0.0, 11.0),
            target=(0.0, 0.0, 0.0),
            up=(0.0, 1.0, 0.0),
            scale=max(10.5, len(cases) * spacing),
        ),
    )
    for index, (angle, polygon, mesh) in enumerate(cases):
        offset = (index - centre) * spacing
        case_name = _min_angle_case_name(angle)
        scene = scene.add(
            _translated_mesh(mesh, offset, 0.0, 0.0),
            name=f"{case_name} triangles",
            style=MESH_STYLES[index % len(MESH_STYLES)],
        )
        scene = scene.add(
            _translated_mesh(_polygon_boundary_overlay(polygon), offset, 0.0, 0.0),
            name=f"{case_name} input polygon",
            style=INPUT_POLYGON_STYLE,
        )
    return scene


def build_shape_scene(cases: tuple[tuple[str, Mesh3, Mesh3], ...]) -> Scene:
    columns = 3
    spacing_x = 5.0
    spacing_y = 3.25
    rows = max(1, ceil(len(cases) / columns))
    scene = Scene(
        "polygon_triangulation_shape_cases",
        camera=Camera.orthographic(
            position=(0.0, 0.0, 15.0),
            target=(0.0, 0.0, 0.0),
            up=(0.0, 1.0, 0.0),
            scale=max(columns * spacing_x, rows * spacing_y) * 1.1,
        ),
    )
    for index, (name, polygon, mesh) in enumerate(cases):
        column = index % columns
        row = index // columns
        x_offset = (column - (columns - 1) / 2.0) * spacing_x
        y_offset = ((rows - 1) / 2.0 - row) * spacing_y
        scene = scene.add(
            _translated_mesh(mesh, x_offset, y_offset, 0.0),
            name=f"{name} heuristic triangles",
            style=MESH_STYLES[index % len(MESH_STYLES)],
        )
        scene = scene.add(
            _translated_mesh(_polygon_boundary_overlay(polygon), x_offset, y_offset, 0.0),
            name=f"{name} input polygon",
            style=INPUT_POLYGON_STYLE,
        )
    return scene


def build_heuristic_scene(polygon: Mesh3, *, tolerance: float = TOLERANCE) -> Scene:
    lower, upper = polygon.bounds()
    centre = (
        (lower[0] + upper[0]) / 2.0,
        (lower[1] + upper[1]) / 2.0,
        (lower[2] + upper[2]) / 2.0,
    )
    span = max(upper[0] - lower[0], upper[1] - lower[1], upper[2] - lower[2], 1.0)
    return (
        Scene(
            "polygon_triangulation_heuristic",
            camera=Camera.orthographic(
                position=(centre[0], centre[1], centre[2] + span * 2.5),
                target=centre,
                up=(0.0, 1.0, 0.0),
                scale=span * 1.25,
            ),
        )
        .add(
            triangulate_polygon_heuristic(polygon, tolerance=tolerance),
            name="heuristic triangles",
            style=HEURISTIC_STYLE,
        )
        .add(_polygon_boundary_overlay(polygon), name="input polygon", style=INPUT_POLYGON_STYLE)
    )


def mesh_summary(cases: tuple[tuple[ResolutionSpec, Mesh3], ...]) -> str:
    lines = ["cady polygon triangulation size comparison"]
    for max_edge_length, mesh in cases:
        lines.append(
            f"{_case_name(max_edge_length)}: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces"
        )
    return "\n".join(lines)


def heuristic_summary(polygon: Mesh3, mesh: Mesh3) -> str:
    return "\n".join(
        (
            "cady polygon heuristic triangulation",
            f"input polygon: {len(polygon.vertices)} vertices, {len(polygon.faces)} face",
            f"heuristic mesh: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces",
        )
    )


def shape_summary(cases: tuple[tuple[str, Mesh3, Mesh3], ...]) -> str:
    lines = ["cady polygon triangulation shape cases"]
    for name, polygon, mesh in cases:
        lines.append(
            f"{name}: {len(polygon.vertices)} boundary vertices -> "
            f"{len(mesh.vertices)} vertices, {len(mesh.faces)} faces"
        )
    return "\n".join(lines)


def min_angle_summary(cases: tuple[tuple[MinAngleSpec, Mesh3, Mesh3], ...]) -> str:
    lines = ["cady skinny polygon min-angle comparison"]
    for angle, polygon, mesh in cases:
        lines.append(
            f"{_min_angle_case_name(angle)}: {len(polygon.vertices)} boundary vertices -> "
            f"{len(mesh.vertices)} vertices, {len(mesh.faces)} faces, "
            f"worst angle {_mesh_min_angle_degrees(mesh):.3g}"
        )
    return "\n".join(lines)


def main() -> None:
    polyline = example_polyline()
    polygon = polygon_mesh_from_polyline(polyline, tolerance=TOLERANCE)
    heuristic_mesh = triangulate_polygon_heuristic(polygon, tolerance=TOLERANCE)
    cases = triangulate_resolutions(polyline)
    shape_cases = triangulate_shape_cases()
    min_angle_cases = triangulate_min_angle_cases()

    print(mesh_summary(cases))
    build_scene(cases).view(
        tolerance=TOLERANCE,
        title="polygon triangulation sizes",
    )

    print()
    print(heuristic_summary(polygon, heuristic_mesh))
    build_heuristic_scene(polygon, tolerance=TOLERANCE).view(
        tolerance=TOLERANCE,
        title="polygon triangulation auto heuristic",
    )
    print()
    print(shape_summary(shape_cases))
    build_shape_scene(shape_cases).view(
        tolerance=TOLERANCE,
        title="polygon triangulation shape cases",
    )
    print()
    print(min_angle_summary(min_angle_cases))
    build_min_angle_scene(min_angle_cases).view(
        tolerance=TOLERANCE,
        title="skinny polygon min angle comparison",
    )
    print("done")


# Example-specific helpers.
def _automatic_guide(
    vertices: tuple[Point3, ...],
    *,
    tolerance: float,
    min_angle_degrees: float | None = None,
) -> TriangulationGuide | None:
    nodes = np.asarray(vertices, dtype=np.float64)
    edges = np.asarray(loop_edges(len(vertices)), dtype=np.int64)
    lengths = np.asarray(
        sorted(length for length in _local_edge_lengths(nodes, edges) if length > tolerance),
        dtype=np.float64,
    )
    if lengths.size == 0:
        return None

    lower = np.min(nodes, axis=0)
    upper = np.max(nodes, axis=0)
    span = float(np.linalg.norm(upper - lower))
    if span <= tolerance:
        return None

    # Size against local boundary features; a global span disables concave detail.
    boundary_feature = float(np.quantile(lengths, 0.40))
    span_feature = span / 5.0
    max_edge_length = max(tolerance * 8.0, min(boundary_feature, span_feature))
    if min_angle_degrees is not None:
        max_edge_length = min(
            max_edge_length,
            _min_angle_edge_length(float(lengths[0]), min_angle_degrees, tolerance=tolerance),
        )
    return TriangulationGuide(max_edge_length=max_edge_length)


def _guide_with_min_angle(
    guide: TriangulationGuide | None,
    min_angle_degrees: float | None,
) -> TriangulationGuide | None:
    if min_angle_degrees is None:
        return guide
    if guide is None:
        return TriangulationGuide(min_angle_degrees=min_angle_degrees)
    return TriangulationGuide(
        target_edge_length=guide.target_edge_length,
        max_edge_length=guide.max_edge_length,
        max_area=guide.max_area,
        min_angle_degrees=min_angle_degrees,
    )


def _min_angle_edge_length(
    shortest_feature: float,
    min_angle_degrees: float,
    *,
    tolerance: float,
) -> float:
    tangent = tan(radians(min_angle_degrees))
    if tangent <= 0.0:
        return max(shortest_feature, tolerance * 8.0)
    return max(shortest_feature / tangent, tolerance * 8.0)


def _local_edge_lengths(nodes: PointArray3, edges: EdgeArray) -> tuple[float, ...]:
    edge_set = {(min(int(start), int(end)), max(int(start), int(end))) for start, end in edges}
    return tuple(float(np.linalg.norm(nodes[start] - nodes[end])) for start, end in edge_set)


def _polygon_face_edges(faces: Iterable[tuple[int, ...]]) -> tuple[EdgeIndex, ...]:
    edges: set[EdgeIndex] = set()
    for face in faces:
        for start, end in zip(face, face[1:] + face[:1], strict=True):
            edges.add((min(start, end), max(start, end)))
    return tuple(sorted(edges))


def _polygon_boundary_overlay(polygon: Mesh3) -> Mesh3:
    vertices = tuple((x, y, z + 0.025) for x, y, z in polygon.vertices)
    return Mesh3(vertices, (), _polygon_face_edges(polygon.faces))


def _translated_mesh(mesh: Mesh3, x_offset: float, y_offset: float, z_offset: float) -> Mesh3:
    return Mesh3(
        tuple((x + x_offset, y + y_offset, z + z_offset) for x, y, z in mesh.vertices),
        mesh.faces,
        mesh.edges,
    )


def _case_name(max_edge_length: ResolutionSpec) -> str:
    if max_edge_length is None:
        return "original boundary"
    if max_edge_length == "auto":
        return "auto guide"
    return f"max edge {max_edge_length:g}"


def _min_angle_case_name(min_angle_degrees: MinAngleSpec) -> str:
    if min_angle_degrees is None:
        return "auto guide"
    return f"min angle {min_angle_degrees:g}"


def _mesh_min_angle_degrees(mesh: Mesh3) -> float:
    return min(
        _triangle_min_angle_degrees(tuple(mesh.vertices[index] for index in face))
        for face in mesh.faces
    )


def _triangle_min_angle_degrees(points: tuple[Point3, Point3, Point3]) -> float:
    a, b, c = points
    ab = _distance3(a, b)
    bc = _distance3(b, c)
    ca = _distance3(c, a)
    return min(
        _angle_degrees(ab, ca, bc),
        _angle_degrees(ab, bc, ca),
        _angle_degrees(bc, ca, ab),
    )


def _distance3(left: Point3, right: Point3) -> float:
    return sqrt(
        (left[0] - right[0]) * (left[0] - right[0])
        + (left[1] - right[1]) * (left[1] - right[1])
        + (left[2] - right[2]) * (left[2] - right[2])
    )


if __name__ == "__main__":
    main()
