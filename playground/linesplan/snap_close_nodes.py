"""Snap nearby mesh nodes together and deduplicate remapped topology."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from math import dist, floor, isfinite
from typing import TypeAlias

from cady import Mesh3

Point3: TypeAlias = tuple[float, float, float]
Face: TypeAlias = tuple[int, ...]
Edge: TypeAlias = tuple[int, int]
Cell: TypeAlias = tuple[int, int, int]


def snap_close_nodes(mesh: Mesh3, *, tolerance: float) -> Mesh3:
    """Return a mesh with close-but-separate nodes snapped into shared vertices."""
    tolerance = _positive_tolerance(tolerance)
    vertices, remap = _snap_vertices(mesh.vertices, tolerance=tolerance)
    faces = _clean_faces(mesh.faces, remap)
    edges = _clean_edges(mesh.edges, remap)
    return Mesh3(vertices, faces, edges)


def _snap_vertices(
    points: Iterable[Point3],
    *,
    tolerance: float,
) -> tuple[tuple[Point3, ...], tuple[int, ...]]:
    cells: dict[Cell, list[int]] = defaultdict(list)
    vertices: list[Point3] = []
    remap: list[int] = []

    for point in points:
        vertex = (float(point[0]), float(point[1]), float(point[2]))
        match = _nearest_existing_vertex(
            vertex,
            vertices,
            cells,
            tolerance=tolerance,
        )
        if match is None:
            match = len(vertices)
            vertices.append(vertex)
            cells[_cell_for_point(vertex, tolerance)].append(match)
        remap.append(match)

    return tuple(vertices), tuple(remap)


def _nearest_existing_vertex(
    point: Point3,
    vertices: list[Point3],
    cells: dict[Cell, list[int]],
    *,
    tolerance: float,
) -> int | None:
    best_index: int | None = None
    best_distance = tolerance

    for cell in _neighbour_cells(_cell_for_point(point, tolerance)):
        for index in cells.get(cell, ()):
            distance = dist(point, vertices[index])
            if distance <= best_distance:
                best_index = index
                best_distance = distance

    return best_index


def _clean_faces(faces: Iterable[Face], remap: tuple[int, ...]) -> tuple[Face, ...]:
    cleaned_faces: list[Face] = []
    seen_faces: set[tuple[int, ...]] = set()

    for face in faces:
        cleaned = _clean_face(face, remap)
        if cleaned is None:
            continue
        key = tuple(sorted(cleaned))
        if key in seen_faces:
            continue
        seen_faces.add(key)
        cleaned_faces.append(cleaned)

    return tuple(cleaned_faces)


def _clean_face(face: Iterable[int], remap: tuple[int, ...]) -> Face | None:
    mapped: list[int] = []
    for index in face:
        new_index = remap[index]
        if not mapped or mapped[-1] != new_index:
            mapped.append(new_index)
    if len(mapped) > 1 and mapped[0] == mapped[-1]:
        mapped.pop()

    unique: list[int] = []
    for index in mapped:
        if index not in unique:
            unique.append(index)

    if len(unique) < 3:
        return None
    return tuple(unique)


def _clean_edges(edges: Iterable[Edge], remap: tuple[int, ...]) -> tuple[Edge, ...]:
    cleaned_edges: set[Edge] = set()
    for start, end in edges:
        remapped_start = remap[start]
        remapped_end = remap[end]
        if remapped_start == remapped_end:
            continue
        cleaned_edges.add(
            (
                min(remapped_start, remapped_end),
                max(remapped_start, remapped_end),
            )
        )
    return tuple(sorted(cleaned_edges))


def _cell_for_point(point: Point3, tolerance: float) -> Cell:
    return (
        floor(point[0] / tolerance),
        floor(point[1] / tolerance),
        floor(point[2] / tolerance),
    )


def _neighbour_cells(cell: Cell) -> Iterable[Cell]:
    x, y, z = cell
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                yield (x + dx, y + dy, z + dz)


def _positive_tolerance(value: float) -> float:
    tolerance = float(value)
    if not isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("tolerance must be positive")
    return tolerance


if __name__ == "__main__":
    raise SystemExit("Run main.py to snap close nodes after building the linesplan mesh.")
