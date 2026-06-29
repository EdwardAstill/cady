"""Topology helpers for indexed triangle and edge meshes."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
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


__all__ = [
    "boundary_edges",
    "boundary_edges_from_faces",
    "compact_mesh_data",
    "edge_loops",
    "prune_dangling_edges",
    "stitch_segments",
]
