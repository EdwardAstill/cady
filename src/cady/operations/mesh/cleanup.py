"""Vertex snapping and index compaction for polygon meshes."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from math import floor
from typing import TypeAlias

from cady.operations.primitives import distance3

Point3: TypeAlias = Sequence[float]
FaceIndex: TypeAlias = tuple[int, ...]
EdgeIndex: TypeAlias = tuple[int, int]


def snap_close_mesh_data(
    points: tuple[Point3, ...],
    faces: tuple[FaceIndex, ...],
    edges: tuple[EdgeIndex, ...],
    *,
    tolerance: float,
) -> tuple[tuple[Point3, ...], tuple[FaceIndex, ...], tuple[EdgeIndex, ...]]:
    """Merge vertices within ``tolerance`` and remap mesh topology."""
    vertices, remap = _snap_close_vertices(points, tolerance=tolerance)
    return vertices, _snap_remap_faces(faces, remap), _snap_remap_edges(edges, remap)


def compact_polygon_mesh(
    vertices: tuple[Point3, ...],
    faces: tuple[FaceIndex, ...],
    edges: tuple[EdgeIndex, ...],
) -> tuple[tuple[Point3, ...], tuple[FaceIndex, ...], tuple[EdgeIndex, ...]]:
    """Remove unused vertices and remap polygon faces and edges."""
    used = sorted(
        {index for face in faces for index in face}
        | {index for edge in edges for index in edge}
    )
    if len(used) == len(vertices) and all(old == new for new, old in enumerate(used)):
        return vertices, faces, edges

    remap = {old: new for new, old in enumerate(used)}
    remapped_faces = tuple(tuple(remap[index] for index in face) for face in faces)
    remapped_edges = tuple(
        sorted(
            _edge_key(remap[start], remap[end])
            for start, end in edges
            if start in remap and end in remap
        )
    )
    return tuple(vertices[index] for index in used), remapped_faces, remapped_edges


def _snap_close_vertices(
    points: tuple[Point3, ...],
    *,
    tolerance: float,
) -> tuple[tuple[Point3, ...], tuple[int, ...]]:
    cells: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    vertices: list[Point3] = []
    remap: list[int] = []

    for point in points:
        vertex = (float(point[0]), float(point[1]), float(point[2]))
        match = _nearest_snap_vertex(vertex, vertices, cells, tolerance=tolerance)
        if match is None:
            match = len(vertices)
            vertices.append(vertex)
            cells[_snap_cell(vertex, tolerance)].append(match)
        remap.append(match)

    return tuple(vertices), tuple(remap)


def _nearest_snap_vertex(
    point: Point3,
    vertices: list[Point3],
    cells: dict[tuple[int, int, int], list[int]],
    *,
    tolerance: float,
) -> int | None:
    best_index: int | None = None
    best_distance = tolerance
    for cell in _snap_neighbour_cells(_snap_cell(point, tolerance)):
        for index in cells.get(cell, ()):
            distance = distance3(point, vertices[index])
            if distance <= best_distance:
                best_index = index
                best_distance = distance
    return best_index


def _snap_cell(point: Point3, tolerance: float) -> tuple[int, int, int]:
    return (
        floor(point[0] / tolerance),
        floor(point[1] / tolerance),
        floor(point[2] / tolerance),
    )


def _snap_neighbour_cells(cell: tuple[int, int, int]) -> Iterable[tuple[int, int, int]]:
    x, y, z = cell
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                yield (x + dx, y + dy, z + dz)


def _snap_remap_faces(
    faces: tuple[FaceIndex, ...],
    remap: tuple[int, ...],
) -> tuple[FaceIndex, ...]:
    cleaned_faces: list[FaceIndex] = []
    seen_faces: set[tuple[int, ...]] = set()

    for face in faces:
        mapped: list[int] = []
        for index in face:
            new_index = remap[index]
            if not mapped or mapped[-1] != new_index:
                mapped.append(new_index)
        if len(mapped) > 1 and mapped[0] == mapped[-1]:
            mapped.pop()
        if len(set(mapped)) < 3:
            continue

        clean = tuple(mapped)
        key = tuple(sorted(clean))
        if key in seen_faces:
            continue
        seen_faces.add(key)
        cleaned_faces.append(clean)

    return tuple(cleaned_faces)


def _snap_remap_edges(
    edges: tuple[EdgeIndex, ...],
    remap: tuple[int, ...],
) -> tuple[EdgeIndex, ...]:
    cleaned_edges: set[EdgeIndex] = set()
    for start, end in edges:
        remapped_start = remap[start]
        remapped_end = remap[end]
        if remapped_start != remapped_end:
            cleaned_edges.add(_edge_key(remapped_start, remapped_end))
    return tuple(sorted(cleaned_edges))


def _edge_key(start: int, end: int) -> EdgeIndex:
    return (min(start, end), max(start, end))

