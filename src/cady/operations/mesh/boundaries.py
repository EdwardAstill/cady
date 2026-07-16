"""Boundary detection and closure for indexed polygon meshes."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray

from cady.errors import GeometryError
from cady.operations.mesh.faces import face_edges

Point: TypeAlias = Sequence[float]
FaceIndex: TypeAlias = tuple[int, ...]
EdgeIndex: TypeAlias = tuple[int, int]
PointArray: TypeAlias = NDArray[np.float64]


def faces_are_closed(faces: tuple[FaceIndex, ...]) -> bool:
    """Return whether every polygon edge belongs to exactly two faces."""
    if not faces:
        return False

    counts: dict[EdgeIndex, int] = {}
    for face in faces:
        indices = tuple(int(index) for index in face)
        for start, end in zip(indices, indices[1:] + indices[:1], strict=True):
            edge = _edge_key(start, end)
            counts[edge] = counts.get(edge, 0) + 1

    return bool(counts) and all(count == 2 for count in counts.values())


def boundary_polylines(
    vertices: tuple[Point, ...],
    faces: tuple[FaceIndex, ...],
) -> tuple[PointArray, ...]:
    """Return closed coordinate polylines for all oriented mesh boundaries."""
    return tuple(
        np.array([vertices[index] for index in loop + [loop[0]]], dtype=np.float64)
        for loop in _boundary_loops(_boundary_halfedges(faces))
    )


def close_planar_boundaries_data(
    vertices: tuple[Point, ...],
    faces: tuple[FaceIndex, ...],
    *,
    tolerance: float,
) -> tuple[tuple[FaceIndex, ...], tuple[EdgeIndex, ...]]:
    """Add one reversed polygon cap for each planar boundary loop."""
    if not faces:
        return faces, ()

    loops = _mesh_boundary_loops(faces)
    if not loops:
        return faces, face_edges(faces)

    cap_faces: list[FaceIndex] = []
    for loop in loops:
        face = tuple(reversed(loop))
        _validate_planar_boundary_loop(vertices, face, tolerance=tolerance)
        cap_faces.append(face)

    closed_faces = (*faces, *cap_faces)
    return closed_faces, face_edges(closed_faces)


def _boundary_halfedges(faces: tuple[FaceIndex, ...]) -> list[EdgeIndex]:
    occurrences: dict[EdgeIndex, list[EdgeIndex]] = defaultdict(list)
    for face in faces:
        indices = [int(index) for index in face]
        for start, end in zip(indices, indices[1:] + indices[:1], strict=True):
            occurrences[_edge_key(start, end)].append((start, end))

    if any(len(edge_occurrences) > 2 for edge_occurrences in occurrences.values()):
        raise GeometryError("mesh boundary is undefined for non-manifold edges")

    return sorted(
        edge_occurrences[0]
        for edge_occurrences in occurrences.values()
        if len(edge_occurrences) == 1
    )


def _boundary_loops(halfedges: list[EdgeIndex]) -> list[list[int]]:
    outgoing: dict[int, int] = {}
    incoming: dict[int, int] = {}
    unused_edges = set(halfedges)

    for start, end in halfedges:
        if start == end:
            raise GeometryError("mesh boundary is not a closed polyline")
        if start in outgoing or end in incoming:
            raise GeometryError("mesh boundary is not a closed polyline")
        outgoing[start] = end
        incoming[end] = start

    if set(outgoing) != set(incoming):
        raise GeometryError("mesh boundary is not a closed polyline")

    loops: list[list[int]] = []
    while unused_edges:
        start, _ = min(unused_edges)
        loop = [start]
        current = start

        while True:
            following = outgoing.get(current)
            if following is None or (current, following) not in unused_edges:
                raise GeometryError("mesh boundary is not a closed polyline")
            unused_edges.remove((current, following))
            current = following
            if current == start:
                break
            if current in loop:
                raise GeometryError("mesh boundary is not a closed polyline")
            loop.append(current)

        if len(loop) < 3:
            raise GeometryError("mesh boundary is not a closed polyline")
        loops.append(loop)

    return sorted(loops, key=lambda loop: (-len(loop), loop))


def _mesh_boundary_loops(faces: tuple[FaceIndex, ...]) -> list[list[int]]:
    halfedges = _boundary_halfedges(faces)
    if not halfedges:
        return []

    neighbours: defaultdict[int, list[int]] = defaultdict(list)
    unused_edges: set[EdgeIndex] = set()
    for start, end in halfedges:
        edge = _edge_key(start, end)
        unused_edges.add(edge)
        neighbours[start].append(end)
        neighbours[end].append(start)

    if any(len(values) != 2 for values in neighbours.values()):
        raise GeometryError("mesh boundary is not a closed polyline")

    loops: list[list[int]] = []
    while unused_edges:
        start = min(index for edge in unused_edges for index in edge)
        loop: list[int] = []
        previous: int | None = None
        current = start

        while True:
            loop.append(current)
            candidates = [
                candidate
                for candidate in sorted(neighbours[current])
                if candidate != previous and _edge_key(current, candidate) in unused_edges
            ]
            if not candidates:
                raise GeometryError("mesh boundary is not a closed polyline")
            following = candidates[0]
            unused_edges.remove(_edge_key(current, following))
            previous, current = current, following
            if current == start:
                break
            if current in loop:
                raise GeometryError("mesh boundary is not a closed polyline")

        if len(loop) < 3:
            raise GeometryError("mesh boundary is not a closed polyline")
        loops.append(loop)

    return sorted(loops, key=lambda loop: (-len(loop), loop))


def _validate_planar_boundary_loop(
    vertices: tuple[Point, ...],
    face: FaceIndex,
    *,
    tolerance: float,
) -> None:
    points = np.asarray([vertices[index] for index in face], dtype=np.float64)
    centroid = points.mean(axis=0)
    centered = points - centroid
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    normal = vt[-1]
    deviation = float(np.max(np.abs(centered @ normal)))
    if deviation > tolerance:
        raise ValueError(
            f"Boundary loop is non-planar (max deviation {deviation:.3e} > "
            f"tolerance {tolerance:.3e})"
        )


def _edge_key(start: int, end: int) -> EdgeIndex:
    return (min(start, end), max(start, end))
