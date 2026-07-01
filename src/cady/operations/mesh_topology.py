"""Topology helpers for indexed triangle and edge meshes."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
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
    "stitch_segments",
]
