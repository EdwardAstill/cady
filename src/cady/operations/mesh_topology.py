"""Small topology utilities for face and edge index data."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

Point3 = tuple[float, float, float]
FaceIndex = tuple[int, int, int]
EdgeIndex = tuple[int, int]


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
