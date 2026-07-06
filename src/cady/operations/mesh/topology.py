"""Topology helpers for indexed triangle and edge meshes."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from math import isfinite
from operator import index as operator_index
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray

Point3: TypeAlias = tuple[float, float, float]
FaceIndex: TypeAlias = tuple[int, int, int]
EdgeIndex: TypeAlias = tuple[int, int]
Segment: TypeAlias = tuple[int, int]
PointArray3 = NDArray[np.float64]
FaceArray = NDArray[np.int64]
EdgeArray = NDArray[np.int64]
MeshArrays: TypeAlias = tuple[PointArray3, FaceArray, EdgeArray]

_EPS = 1e-12


def boundary_edges(mesh: MeshArrays) -> list[Segment]:
    """Return edges that appear in exactly one face."""
    _vertices, faces, _edges = mesh
    counts: Counter[tuple[int, int]] = Counter()
    for face in faces:
        indices = [int(face[0]), int(face[1]), int(face[2])]
        for start, end in zip(indices, indices[1:] + indices[:1], strict=True):
            counts[(min(start, end), max(start, end))] += 1
    return [(a, b) for (a, b), count in counts.items() if count == 1]


def boundary_edges_from_faces(faces: Sequence[FaceIndex]) -> tuple[EdgeIndex, ...]:
    """Return undirected edges referenced by exactly one triangle."""
    counts: dict[EdgeIndex, int] = {}
    for a, b, c in faces:
        for start, end in ((a, b), (b, c), (c, a)):
            edge = (min(start, end), max(start, end))
            counts[edge] = counts.get(edge, 0) + 1
    return tuple(edge for edge, count in counts.items() if count == 1)


def stitch_segments(segments: Iterable[Segment]) -> list[list[int]]:
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


def edge_loops(edges: object) -> tuple[tuple[int, ...], ...]:
    """Return closed vertex loops from undirected edge constraints."""
    edges_array = np.asarray(edges, dtype=np.int64)
    if edges_array.size == 0:
        return ()
    if edges_array.ndim != 2 or edges_array.shape[1] != 2:
        raise ValueError("edges must have shape (n, 2)")
    return tuple(tuple(loop) for loop in stitch_segments((int(a), int(b)) for a, b in edges_array))


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
        live_edges = [(a, b) for a, b in live_edges if a in live_vertices and b in live_vertices]

    return tuple(live_edges)


def decimate_mesh_data(
    vertices: object,
    faces: object,
    edges: object | None = None,
    *,
    target_faces: int,
    tolerance: float = 1e-9,
) -> MeshArrays:
    """Simplify a triangle mesh with deterministic shortest-edge collapses."""
    target_count = _target_face_count(target_faces)
    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive")

    vertices_array = _points3_array(vertices)
    faces_array = _face_array(faces, vertex_count=len(vertices_array))
    edges_array = _edge_array(edges, vertex_count=len(vertices_array))

    if len(faces_array) <= target_count:
        return vertices_array.copy(), faces_array.copy(), edges_array.copy()

    live_vertices = vertices_array.copy()
    live_faces: list[FaceIndex] = [
        (int(face[0]), int(face[1]), int(face[2])) for face in faces_array
    ]
    live_edges: list[EdgeIndex] = [
        (int(edge[0]), int(edge[1])) for edge in edges_array
    ]

    while len(live_faces) > target_count:
        collapse_edge = _shortest_edge(live_vertices, live_faces)
        if collapse_edge is None:
            break

        next_faces, next_edges = _collapse_edge(
            live_vertices,
            live_faces,
            live_edges,
            collapse_edge,
        )
        if len(next_faces) >= len(live_faces):
            break
        live_faces = next_faces
        live_edges = next_edges

    compact_vertices, compact_faces, compact_edges = compact_mesh_data(
        _points_from_array(live_vertices),
        live_faces,
        live_edges,
    )
    return (
        _vertices_array(compact_vertices),
        _faces_array(compact_faces),
        _edges_array(compact_edges),
    )


def remesh_mesh_data(
    vertices: object,
    faces: object,
    edges: object | None = None,
    *,
    target_edge_length: float | None = None,
    iterations: int = 10,
    feature_angle_degrees: float | None = 50.0,
    protect_boundary: bool = True,
    long_factor: float = 4.0 / 3.0,
    short_factor: float = 4.0 / 5.0,
    relaxation: float = 0.5,
    project: bool = True,
    tolerance: float = 1e-9,
) -> MeshArrays:
    """Remesh a triangle surface toward isotropic edge lengths."""
    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive")

    iteration_count = _remesh_iteration_count(iterations)
    target_length = _remesh_optional_positive(target_edge_length, "target_edge_length")
    feature_angle = _remesh_feature_angle(feature_angle_degrees)
    long_threshold = _remesh_positive(long_factor, "long_factor")
    short_threshold = _remesh_positive(short_factor, "short_factor")
    relax = _remesh_relaxation(relaxation)

    if long_threshold <= 1.0:
        raise ValueError("long_factor must be greater than 1")
    if short_threshold >= 1.0:
        raise ValueError("short_factor must be less than 1")

    vertices_array = _points3_array(vertices)
    faces_array = _face_array(faces, vertex_count=len(vertices_array))
    edges_array = _edge_array(edges, vertex_count=len(vertices_array))

    if len(faces_array) == 0:
        return vertices_array.copy(), faces_array.copy(), edges_array.copy()

    area_eps = max(_EPS, float(tolerance) * float(tolerance))
    remesh_vertices = vertices_array.copy()
    remesh_faces = _remove_degenerate_faces(remesh_vertices, faces_array, area_eps=area_eps)
    remesh_vertices, remesh_faces = _compact_triangle_mesh(remesh_vertices, remesh_faces)

    if len(remesh_faces) == 0:
        return remesh_vertices, remesh_faces, np.empty((0, 2), dtype=np.int64)

    original_vertices = remesh_vertices.copy()
    original_faces = remesh_faces.copy()

    if target_length is None:
        lengths = _edge_lengths(remesh_vertices, _unique_edges(remesh_faces))
        if len(lengths) == 0:
            return remesh_vertices, remesh_faces, np.empty((0, 2), dtype=np.int64)
        target_length = float(np.mean(lengths))

    for _index in range(iteration_count):
        remesh_vertices, remesh_faces, _split_count = _split_long_edges(
            remesh_vertices,
            remesh_faces,
            target_length,
            long_factor=long_threshold,
            area_eps=area_eps,
        )
        remesh_vertices, remesh_faces = _compact_triangle_mesh(
            remesh_vertices,
            _remove_degenerate_faces(remesh_vertices, remesh_faces, area_eps=area_eps),
        )

        _protected_edges, protected_vertices = _protected_edges_and_vertices(
            remesh_vertices,
            remesh_faces,
            feature_angle_degrees=feature_angle,
            protect_boundary=protect_boundary,
        )
        remesh_vertices, remesh_faces, _collapse_count = _collapse_short_edges(
            remesh_vertices,
            remesh_faces,
            target_length,
            protected_vertices=protected_vertices,
            short_factor=short_threshold,
            area_eps=area_eps,
        )

        protected_edges, protected_vertices = _protected_edges_and_vertices(
            remesh_vertices,
            remesh_faces,
            feature_angle_degrees=feature_angle,
            protect_boundary=protect_boundary,
        )
        remesh_vertices, remesh_faces, _flip_count = _flip_edges(
            remesh_vertices,
            remesh_faces,
            protected_edges=protected_edges,
            protected_vertices=protected_vertices,
            area_eps=area_eps,
        )

        _protected_edges, protected_vertices = _protected_edges_and_vertices(
            remesh_vertices,
            remesh_faces,
            feature_angle_degrees=feature_angle,
            protect_boundary=protect_boundary,
        )
        remesh_vertices = _smooth_vertices(
            remesh_vertices,
            remesh_faces,
            protected_vertices=protected_vertices,
            relaxation=relax,
            project_vertices=original_vertices if project else None,
            project_faces=original_faces if project else None,
        )
        remesh_vertices, remesh_faces = _compact_triangle_mesh(
            remesh_vertices,
            _remove_degenerate_faces(remesh_vertices, remesh_faces, area_eps=area_eps),
        )

        if len(remesh_faces) == 0:
            break

    return remesh_vertices, remesh_faces, _unique_edges(remesh_faces)


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


def _target_face_count(target_faces: int) -> int:
    try:
        count = operator_index(target_faces)
    except TypeError as exc:
        raise TypeError("target_faces must be an integer") from exc
    if count < 1:
        raise ValueError("target_faces must be positive")
    return count


def _remesh_iteration_count(iterations: int) -> int:
    try:
        count = operator_index(iterations)
    except TypeError as exc:
        raise TypeError("iterations must be an integer") from exc
    if count < 0:
        raise ValueError("iterations must be non-negative")
    return count


def _remesh_optional_positive(value: float | None, name: str) -> float | None:
    if value is None:
        return None
    return _remesh_positive(value, name)


def _remesh_positive(value: float, name: str) -> float:
    number = float(value)
    if not isfinite(number) or number <= 0.0:
        raise ValueError(f"{name} must be positive")
    return number


def _remesh_feature_angle(value: float | None) -> float | None:
    if value is None:
        return None
    angle = float(value)
    if not isfinite(angle) or angle < 0.0 or angle > 180.0:
        raise ValueError("feature_angle_degrees must be between 0 and 180")
    return angle


def _remesh_relaxation(value: float) -> float:
    relaxation = float(value)
    if not isfinite(relaxation) or relaxation < 0.0 or relaxation > 1.0:
        raise ValueError("relaxation must be between 0 and 1")
    return relaxation


def _edge_key(start: int, end: int) -> EdgeIndex:
    a = int(start)
    b = int(end)
    return (a, b) if a < b else (b, a)


def _unique_edges(faces: FaceArray) -> EdgeArray:
    if len(faces) == 0:
        return np.empty((0, 2), dtype=np.int64)

    edges = np.vstack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    edges.sort(axis=1)
    return np.unique(edges, axis=0).astype(np.int64, copy=False)


def _edge_lengths(vertices: PointArray3, edges: EdgeArray) -> NDArray[np.float64]:
    if len(edges) == 0:
        return np.empty(0, dtype=np.float64)
    return np.linalg.norm(vertices[edges[:, 1]] - vertices[edges[:, 0]], axis=1)


def _face_normals(vertices: PointArray3, faces: FaceArray, *, unit: bool) -> PointArray3:
    if len(faces) == 0:
        return np.empty((0, 3), dtype=np.float64)

    normals = np.cross(
        vertices[faces[:, 1]] - vertices[faces[:, 0]],
        vertices[faces[:, 2]] - vertices[faces[:, 0]],
    )
    if not unit:
        return normals

    lengths = np.linalg.norm(normals, axis=1)
    output = np.zeros_like(normals)
    good = lengths > _EPS
    output[good] = normals[good] / lengths[good, None]
    return output


def _vertex_normals(vertices: PointArray3, faces: FaceArray) -> PointArray3:
    normals = np.zeros_like(vertices)
    if len(faces) == 0:
        return normals

    face_normals = _face_normals(vertices, faces, unit=False)
    np.add.at(normals, faces[:, 0], face_normals)
    np.add.at(normals, faces[:, 1], face_normals)
    np.add.at(normals, faces[:, 2], face_normals)

    lengths = np.linalg.norm(normals, axis=1)
    good = lengths > _EPS
    normals[good] /= lengths[good, None]
    return normals


def _triangle_quality(vertices: PointArray3, faces: FaceArray) -> NDArray[np.float64]:
    if len(faces) == 0:
        return np.empty(0, dtype=np.float64)

    a = vertices[faces[:, 0]]
    b = vertices[faces[:, 1]]
    c = vertices[faces[:, 2]]

    ab = np.linalg.norm(b - a, axis=1)
    bc = np.linalg.norm(c - b, axis=1)
    ca = np.linalg.norm(a - c, axis=1)
    area2 = np.linalg.norm(np.cross(b - a, c - a), axis=1)
    denominator = ab * ab + bc * bc + ca * ca

    quality = np.zeros(len(faces), dtype=np.float64)
    good = denominator > _EPS
    quality[good] = 2.0 * np.sqrt(3.0) * area2[good] / denominator[good]
    return np.clip(quality, 0.0, 1.0)


def _remove_degenerate_faces(
    vertices: PointArray3,
    faces: FaceArray,
    *,
    area_eps: float,
) -> FaceArray:
    if len(faces) == 0:
        return np.empty((0, 3), dtype=np.int64)

    non_repeated = (
        (faces[:, 0] != faces[:, 1])
        & (faces[:, 1] != faces[:, 2])
        & (faces[:, 2] != faces[:, 0])
    )
    faces = faces[non_repeated]
    if len(faces) == 0:
        return np.empty((0, 3), dtype=np.int64)

    normals = _face_normals(vertices, faces, unit=False)
    faces = faces[np.linalg.norm(normals, axis=1) > area_eps]
    if len(faces) == 0:
        return np.empty((0, 3), dtype=np.int64)

    sorted_faces = np.sort(faces, axis=1)
    _unique, keep = np.unique(sorted_faces, axis=0, return_index=True)
    return faces[np.sort(keep)].astype(np.int64, copy=False)


def _compact_triangle_mesh(
    vertices: PointArray3,
    faces: FaceArray,
) -> tuple[PointArray3, FaceArray]:
    if len(faces) == 0:
        return vertices[:0].copy(), np.empty((0, 3), dtype=np.int64)

    used = np.unique(faces.ravel())
    remap = -np.ones(len(vertices), dtype=np.int64)
    remap[used] = np.arange(len(used), dtype=np.int64)
    return vertices[used].copy(), remap[faces]


def _edge_faces(faces: FaceArray) -> dict[EdgeIndex, list[int]]:
    edge_faces: dict[EdgeIndex, list[int]] = {}
    for face_index, face in enumerate(faces):
        a, b, c = int(face[0]), int(face[1]), int(face[2])
        for start, end in ((a, b), (b, c), (c, a)):
            edge_faces.setdefault(_edge_key(start, end), []).append(face_index)
    return edge_faces


def _vertex_faces(faces: FaceArray, vertex_count: int) -> list[list[int]]:
    vertex_faces: list[list[int]] = [[] for _index in range(vertex_count)]
    for face_index, face in enumerate(faces):
        for vertex_index in face:
            vertex_faces[int(vertex_index)].append(face_index)
    return vertex_faces


def _vertex_neighbors(faces: FaceArray, vertex_count: int) -> list[set[int]]:
    neighbors: list[set[int]] = [set() for _index in range(vertex_count)]
    for face in faces:
        a, b, c = int(face[0]), int(face[1]), int(face[2])
        neighbors[a].update((b, c))
        neighbors[b].update((a, c))
        neighbors[c].update((a, b))
    return neighbors


def _protected_edges_and_vertices(
    vertices: PointArray3,
    faces: FaceArray,
    *,
    feature_angle_degrees: float | None,
    protect_boundary: bool,
) -> tuple[set[EdgeIndex], NDArray[np.bool_]]:
    edge_faces = _edge_faces(faces)
    face_normals = _face_normals(vertices, faces, unit=True)
    protected_edges: set[EdgeIndex] = set()
    cos_limit = (
        None if feature_angle_degrees is None else float(np.cos(np.deg2rad(feature_angle_degrees)))
    )

    for edge, face_indices in edge_faces.items():
        if len(face_indices) == 1:
            if protect_boundary:
                protected_edges.add(edge)
        elif len(face_indices) == 2:
            if cos_limit is not None:
                dot = float(np.dot(face_normals[face_indices[0]], face_normals[face_indices[1]]))
                if dot < cos_limit:
                    protected_edges.add(edge)
        else:
            protected_edges.add(edge)

    protected_vertices = np.zeros(len(vertices), dtype=np.bool_)
    for start, end in protected_edges:
        protected_vertices[start] = True
        protected_vertices[end] = True
    return protected_edges, protected_vertices


def _split_long_edges(
    vertices: PointArray3,
    faces: FaceArray,
    target_edge_length: float,
    *,
    long_factor: float,
    area_eps: float,
) -> tuple[PointArray3, FaceArray, int]:
    edges = _unique_edges(faces)
    lengths = _edge_lengths(vertices, edges)
    long_edges = edges[lengths > long_factor * target_edge_length]
    if len(long_edges) == 0:
        return vertices.copy(), faces.copy(), 0

    split_map: dict[EdgeIndex, int] = {}
    new_vertices: list[NDArray[np.float64]] = []
    for edge in long_edges:
        start, end = int(edge[0]), int(edge[1])
        split_map[_edge_key(start, end)] = len(vertices) + len(new_vertices)
        new_vertices.append(0.5 * (vertices[start] + vertices[end]))

    vertices_out = np.vstack((vertices, np.asarray(new_vertices, dtype=np.float64)))
    new_faces: list[FaceIndex] = []

    for face in faces:
        a, b, c = int(face[0]), int(face[1]), int(face[2])
        m_ab = split_map.get(_edge_key(a, b))
        m_bc = split_map.get(_edge_key(b, c))
        m_ca = split_map.get(_edge_key(c, a))
        split_count = int(m_ab is not None) + int(m_bc is not None) + int(m_ca is not None)

        if split_count == 0:
            new_faces.append((a, b, c))
        elif split_count == 1:
            if m_ab is not None:
                new_faces.extend(((a, m_ab, c), (m_ab, b, c)))
            elif m_bc is not None:
                new_faces.extend(((b, m_bc, a), (m_bc, c, a)))
            elif m_ca is not None:
                new_faces.extend(((c, m_ca, b), (m_ca, a, b)))
        elif split_count == 2:
            if m_ab is not None and m_bc is not None:
                new_faces.extend(((m_ab, b, m_bc), (a, m_ab, c), (m_ab, m_bc, c)))
            elif m_bc is not None and m_ca is not None:
                new_faces.extend(((m_bc, c, m_ca), (b, m_bc, a), (m_bc, m_ca, a)))
            elif m_ca is not None and m_ab is not None:
                new_faces.extend(((m_ca, a, m_ab), (c, m_ca, b), (m_ca, m_ab, b)))
        elif m_ab is not None and m_bc is not None and m_ca is not None:
            new_faces.extend(
                ((a, m_ab, m_ca), (m_ab, b, m_bc), (m_ca, m_bc, c), (m_ab, m_bc, m_ca))
            )

    faces_out = _remove_degenerate_faces(
        vertices_out,
        np.asarray(new_faces, dtype=np.int64),
        area_eps=area_eps,
    )
    return vertices_out, faces_out, len(long_edges)


def _collapse_topology_ok(
    faces: FaceArray,
    edge_faces: dict[EdgeIndex, list[int]],
    neighbors: list[set[int]],
    start: int,
    end: int,
) -> bool:
    face_indices = edge_faces.get(_edge_key(start, end), [])
    if len(face_indices) != 2:
        return False

    common = neighbors[start].intersection(neighbors[end])
    opposite: set[int] = set()
    for face_index in face_indices:
        for vertex_index in faces[face_index]:
            index = int(vertex_index)
            if index != start and index != end:
                opposite.add(index)
    return common == opposite


def _collapse_geometry_ok(
    vertices: PointArray3,
    faces: FaceArray,
    vertex_faces: list[list[int]],
    unit_face_normals: PointArray3,
    start: int,
    end: int,
    new_point: NDArray[np.float64],
    *,
    area_eps: float,
    min_normal_dot: float,
) -> bool:
    affected_faces = set(vertex_faces[start] + vertex_faces[end])
    for face_index in affected_faces:
        face = faces[face_index]
        has_start = bool(np.any(face == start))
        has_end = bool(np.any(face == end))

        if has_start and has_end:
            continue

        points: list[NDArray[np.float64]] = []
        ids: list[int] = []
        for vertex_index in face:
            index = int(vertex_index)
            if index in (start, end):
                points.append(new_point)
                ids.append(start)
            else:
                points.append(vertices[index])
                ids.append(index)

        if len(set(ids)) < 3:
            return False

        normal = np.cross(points[1] - points[0], points[2] - points[0])
        normal_length = float(np.linalg.norm(normal))
        if normal_length <= area_eps:
            return False

        old_normal = unit_face_normals[face_index]
        if (
            float(np.linalg.norm(old_normal)) > _EPS
            and float(np.dot(normal / normal_length, old_normal)) < min_normal_dot
        ):
            return False

    return True


def _collapse_short_edges(
    vertices: PointArray3,
    faces: FaceArray,
    target_edge_length: float,
    *,
    protected_vertices: NDArray[np.bool_],
    short_factor: float,
    area_eps: float,
    min_normal_dot: float = 0.0,
) -> tuple[PointArray3, FaceArray, int]:
    edges = _unique_edges(faces)
    lengths = _edge_lengths(vertices, edges)
    order = np.argsort(lengths)

    edge_faces = _edge_faces(faces)
    vertex_faces = _vertex_faces(faces, len(vertices))
    neighbors = _vertex_neighbors(faces, len(vertices))
    face_normals = _face_normals(vertices, faces, unit=True)

    touched = np.zeros(len(vertices), dtype=np.bool_)
    selected: list[tuple[int, int, NDArray[np.float64]]] = []

    for edge_index in order:
        if float(lengths[int(edge_index)]) >= short_factor * target_edge_length:
            break

        start, end = int(edges[edge_index, 0]), int(edges[edge_index, 1])
        if bool(protected_vertices[start]) or bool(protected_vertices[end]):
            continue
        if bool(touched[start]) or bool(touched[end]):
            continue
        if not _collapse_topology_ok(faces, edge_faces, neighbors, start, end):
            continue

        new_point = 0.5 * (vertices[start] + vertices[end])
        if not _collapse_geometry_ok(
            vertices,
            faces,
            vertex_faces,
            face_normals,
            start,
            end,
            new_point,
            area_eps=area_eps,
            min_normal_dot=min_normal_dot,
        ):
            continue

        selected.append((start, end, new_point))
        touched[start] = True
        touched[end] = True

    if not selected:
        return vertices.copy(), faces.copy(), 0

    vertices_out = vertices.copy()
    replace = np.arange(len(vertices), dtype=np.int64)
    for keep, remove, point in selected:
        vertices_out[keep] = point
        replace[remove] = keep

    faces_out = _remove_degenerate_faces(vertices_out, replace[faces], area_eps=area_eps)
    vertices_out, faces_out = _compact_triangle_mesh(vertices_out, faces_out)
    return vertices_out, faces_out, len(selected)


def _orient_face_to_normal(
    vertices: PointArray3,
    face: tuple[int, int, int],
    target_normal: NDArray[np.float64],
) -> NDArray[np.int64]:
    face_array = np.asarray(face, dtype=np.int64)
    normal = np.cross(
        vertices[face_array[1]] - vertices[face_array[0]],
        vertices[face_array[2]] - vertices[face_array[0]],
    )
    if float(np.dot(normal, target_normal)) < 0.0:
        return np.asarray((face_array[0], face_array[2], face_array[1]), dtype=np.int64)
    return face_array


def _flip_edges(
    vertices: PointArray3,
    faces: FaceArray,
    *,
    protected_edges: set[EdgeIndex],
    protected_vertices: NDArray[np.bool_],
    area_eps: float,
    min_quality_ratio: float = 0.8,
    min_normal_dot: float = 0.0,
) -> tuple[PointArray3, FaceArray, int]:
    edge_faces = _edge_faces(faces)
    neighbors = _vertex_neighbors(faces, len(vertices))
    valence = np.asarray([len(values) for values in neighbors], dtype=np.int64)
    face_normals = _face_normals(vertices, faces, unit=True)
    faces_out = faces.copy()

    touched_vertices: set[int] = set()
    flipped_count = 0

    for edge, face_indices in edge_faces.items():
        if len(face_indices) != 2 or edge in protected_edges:
            continue

        face_index1, face_index2 = face_indices
        tri1 = faces[face_index1]
        tri2 = faces[face_index2]
        a, b = edge

        c_candidates = [int(index) for index in tri1 if int(index) != a and int(index) != b]
        d_candidates = [int(index) for index in tri2 if int(index) != a and int(index) != b]
        if len(c_candidates) != 1 or len(d_candidates) != 1:
            continue

        c = c_candidates[0]
        d = d_candidates[0]
        if c == d:
            continue
        if any(bool(protected_vertices[index]) for index in (a, b, c, d)):
            continue
        if any(index in touched_vertices for index in (a, b, c, d)):
            continue

        new_edge = _edge_key(c, d)
        if new_edge in edge_faces:
            continue

        before = (
            (valence[a] - 6) ** 2
            + (valence[b] - 6) ** 2
            + (valence[c] - 6) ** 2
            + (valence[d] - 6) ** 2
        )
        after = (
            (valence[a] - 7) ** 2
            + (valence[b] - 7) ** 2
            + (valence[c] - 5) ** 2
            + (valence[d] - 5) ** 2
        )
        if after >= before:
            continue

        old_quality = _triangle_quality(vertices, np.vstack((tri1, tri2)))
        old_min_quality = float(np.min(old_quality)) if len(old_quality) else 0.0
        average_normal = face_normals[face_index1] + face_normals[face_index2]
        average_normal_length = float(np.linalg.norm(average_normal))
        if average_normal_length < _EPS:
            continue

        new_face1 = _orient_face_to_normal(vertices, (c, d, a), average_normal)
        new_face2 = _orient_face_to_normal(vertices, (d, c, b), average_normal)
        new_quality = _triangle_quality(vertices, np.vstack((new_face1, new_face2)))
        new_min_quality = float(np.min(new_quality)) if len(new_quality) else 0.0
        if new_min_quality + 1e-14 < min_quality_ratio * old_min_quality:
            continue

        average_normal_unit = average_normal / average_normal_length
        if not _flipped_faces_are_valid(
            vertices,
            (new_face1, new_face2),
            average_normal_unit,
            area_eps=area_eps,
            min_normal_dot=min_normal_dot,
        ):
            continue

        faces_out[face_index1] = new_face1
        faces_out[face_index2] = new_face2
        touched_vertices.update((a, b, c, d))
        flipped_count += 1

    if flipped_count == 0:
        return vertices.copy(), faces.copy(), 0

    return (
        vertices.copy(),
        _remove_degenerate_faces(vertices, faces_out, area_eps=area_eps),
        flipped_count,
    )


def _flipped_faces_are_valid(
    vertices: PointArray3,
    faces: tuple[NDArray[np.int64], NDArray[np.int64]],
    average_normal: NDArray[np.float64],
    *,
    area_eps: float,
    min_normal_dot: float,
) -> bool:
    for face in faces:
        normal = np.cross(
            vertices[face[1]] - vertices[face[0]],
            vertices[face[2]] - vertices[face[0]],
        )
        normal_length = float(np.linalg.norm(normal))
        if normal_length <= area_eps:
            return False
        if float(np.dot(normal / normal_length, average_normal)) < min_normal_dot:
            return False
    return True


def _closest_points_on_segments(
    point: NDArray[np.float64],
    starts: PointArray3,
    ends: PointArray3,
) -> PointArray3:
    segments = ends - starts
    denominator = np.sum(segments * segments, axis=1)
    denominator_safe = np.where(denominator > _EPS, denominator, 1.0)
    parameter = np.sum((point[None, :] - starts) * segments, axis=1) / denominator_safe
    parameter = np.clip(parameter, 0.0, 1.0)
    return starts + parameter[:, None] * segments


def _closest_point_on_triangle_mesh(
    point: NDArray[np.float64],
    vertices: PointArray3,
    faces: FaceArray,
) -> NDArray[np.float64]:
    a = vertices[faces[:, 0]]
    b = vertices[faces[:, 1]]
    c = vertices[faces[:, 2]]

    ab = b - a
    ac = c - a
    normals = np.cross(ab, ac)
    normal_lengths2 = np.sum(normals * normals, axis=1)
    normal_lengths2_safe = np.where(normal_lengths2 > _EPS, normal_lengths2, 1.0)

    ap = point[None, :] - a
    tplane = np.sum(ap * normals, axis=1) / normal_lengths2_safe
    projected = point[None, :] - tplane[:, None] * normals

    v0 = ab
    v1 = ac
    v2 = projected - a
    d00 = np.sum(v0 * v0, axis=1)
    d01 = np.sum(v0 * v1, axis=1)
    d11 = np.sum(v1 * v1, axis=1)
    d20 = np.sum(v2 * v0, axis=1)
    d21 = np.sum(v2 * v1, axis=1)

    denominator = d00 * d11 - d01 * d01
    denominator_safe = np.where(np.abs(denominator) > _EPS, denominator, 1.0)
    vb = (d11 * d20 - d01 * d21) / denominator_safe
    wb = (d00 * d21 - d01 * d20) / denominator_safe
    ub = 1.0 - vb - wb

    inside = (
        (normal_lengths2 > _EPS)
        & (np.abs(denominator) > _EPS)
        & (ub >= -1e-12)
        & (vb >= -1e-12)
        & (wb >= -1e-12)
    )

    cp_ab = _closest_points_on_segments(point, a, b)
    cp_bc = _closest_points_on_segments(point, b, c)
    cp_ca = _closest_points_on_segments(point, c, a)

    closest_points = cp_ab.copy()
    distances2 = np.sum((cp_ab - point[None, :]) ** 2, axis=1)

    next_distances2 = np.sum((cp_bc - point[None, :]) ** 2, axis=1)
    mask = next_distances2 < distances2
    closest_points[mask] = cp_bc[mask]
    distances2[mask] = next_distances2[mask]

    next_distances2 = np.sum((cp_ca - point[None, :]) ** 2, axis=1)
    mask = next_distances2 < distances2
    closest_points[mask] = cp_ca[mask]
    distances2[mask] = next_distances2[mask]

    plane_distances2 = np.sum((projected - point[None, :]) ** 2, axis=1)
    mask = inside & (plane_distances2 <= distances2)
    closest_points[mask] = projected[mask]
    distances2[mask] = plane_distances2[mask]

    return closest_points[int(np.argmin(distances2))]


def _project_points_to_mesh(
    points: PointArray3,
    vertices: PointArray3,
    faces: FaceArray,
) -> PointArray3:
    projected = np.empty_like(points)
    for index in range(len(points)):
        projected[index] = _closest_point_on_triangle_mesh(points[index], vertices, faces)
    return projected


def _smooth_vertices(
    vertices: PointArray3,
    faces: FaceArray,
    *,
    protected_vertices: NDArray[np.bool_],
    relaxation: float,
    project_vertices: PointArray3 | None = None,
    project_faces: FaceArray | None = None,
) -> PointArray3:
    neighbors = _vertex_neighbors(faces, len(vertices))
    vertex_normals = _vertex_normals(vertices, faces)
    vertices_out = vertices.copy()
    movable_indices: list[int] = []

    for index in range(len(vertices)):
        if bool(protected_vertices[index]) or not neighbors[index]:
            continue

        neighbor_indices = np.fromiter(neighbors[index], dtype=np.int64)
        centroid = np.mean(vertices[neighbor_indices], axis=0)
        delta = centroid - vertices[index]
        normal = vertex_normals[index]
        if float(np.linalg.norm(normal)) > _EPS:
            delta = delta - np.dot(delta, normal) * normal
        vertices_out[index] = vertices[index] + relaxation * delta
        movable_indices.append(index)

    if project_vertices is not None and project_faces is not None and movable_indices:
        indices = np.asarray(movable_indices, dtype=np.int64)
        vertices_out[indices] = _project_points_to_mesh(
            vertices_out[indices],
            project_vertices,
            project_faces,
        )

    return vertices_out


def _points3_array(vertices: object) -> PointArray3:
    array = np.asarray(vertices, dtype=np.float64)
    if array.size == 0:
        return np.empty((0, 3), dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("vertices must have shape (n, 3)")
    return np.array(array, dtype=np.float64, copy=True)


def _face_array(faces: object, *, vertex_count: int) -> FaceArray:
    array = np.asarray(faces, dtype=np.int64)
    if array.size == 0:
        return np.empty((0, 3), dtype=np.int64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("faces must have shape (n, 3)")
    _validate_indices(array, vertex_count=vertex_count, name="faces")
    return np.array(array, dtype=np.int64, copy=True)


def _edge_array(edges: object | None, *, vertex_count: int) -> EdgeArray:
    array = np.asarray(
        np.empty((0, 2), dtype=np.int64) if edges is None else edges,
        dtype=np.int64,
    )
    if array.size == 0:
        return np.empty((0, 2), dtype=np.int64)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError("edges must have shape (n, 2)")
    _validate_indices(array, vertex_count=vertex_count, name="edges")
    return np.array(array, dtype=np.int64, copy=True)


def _validate_indices(array: NDArray[np.int64], *, vertex_count: int, name: str) -> None:
    if len(array) == 0:
        return
    if int(np.min(array)) < 0:
        raise ValueError(f"{name} must not contain negative indices")
    if vertex_count == 0 or int(np.max(array)) >= vertex_count:
        raise ValueError(f"{name} reference vertices outside the vertex array")


def _shortest_edge(vertices: PointArray3, faces: Sequence[FaceIndex]) -> EdgeIndex | None:
    best_edge: EdgeIndex | None = None
    best_length = float("inf")
    for edge in _mesh_edges(faces):
        a, b = edge
        length = float(np.linalg.norm(vertices[a] - vertices[b]))
        if length < best_length:
            best_edge = edge
            best_length = length
    return best_edge


def _mesh_edges(faces: Sequence[FaceIndex]) -> tuple[EdgeIndex, ...]:
    edges: set[EdgeIndex] = set()
    for a, b, c in faces:
        for start, end in ((a, b), (b, c), (c, a)):
            edges.add((min(start, end), max(start, end)))
    return tuple(sorted(edges))


def _collapse_edge(
    vertices: PointArray3,
    faces: Sequence[FaceIndex],
    edges: Sequence[EdgeIndex],
    collapse_edge: EdgeIndex,
) -> tuple[list[FaceIndex], list[EdgeIndex]]:
    keep, remove = min(collapse_edge), max(collapse_edge)
    vertices[keep] = (vertices[keep] + vertices[remove]) * 0.5

    next_faces: list[FaceIndex] = []
    seen_faces: set[FaceIndex] = set()
    for face in faces:
        remapped = tuple(keep if index == remove else index for index in face)
        if len(set(remapped)) < 3:
            continue
        face_value = (int(remapped[0]), int(remapped[1]), int(remapped[2]))
        sorted_face = sorted(face_value)
        face_key = (sorted_face[0], sorted_face[1], sorted_face[2])
        if face_key in seen_faces:
            continue
        seen_faces.add(face_key)
        next_faces.append(face_value)

    next_edges: list[EdgeIndex] = []
    seen_edges: set[EdgeIndex] = set()
    for a, b in edges:
        remapped = (
            keep if a == remove else int(a),
            keep if b == remove else int(b),
        )
        if remapped[0] == remapped[1]:
            continue
        edge_value = (min(remapped[0], remapped[1]), max(remapped[0], remapped[1]))
        if edge_value in seen_edges:
            continue
        seen_edges.add(edge_value)
        next_edges.append(edge_value)

    return next_faces, next_edges


def _points_from_array(vertices: PointArray3) -> tuple[Point3, ...]:
    return tuple((float(x), float(y), float(z)) for x, y, z in vertices)


def _vertices_array(vertices: Sequence[Point3]) -> PointArray3:
    if not vertices:
        return np.empty((0, 3), dtype=np.float64)
    return np.array(vertices, dtype=np.float64)


def _faces_array(faces: Sequence[FaceIndex]) -> FaceArray:
    if not faces:
        return np.empty((0, 3), dtype=np.int64)
    return np.array(faces, dtype=np.int64)


def _edges_array(edges: Sequence[EdgeIndex]) -> EdgeArray:
    if not edges:
        return np.empty((0, 2), dtype=np.int64)
    return np.array(edges, dtype=np.int64)


__all__ = [
    "boundary_edges",
    "boundary_edges_from_faces",
    "compact_mesh_data",
    "decimate_mesh_data",
    "edge_loops",
    "prune_dangling_edges",
    "remesh_mesh_data",
    "stitch_segments",
]
