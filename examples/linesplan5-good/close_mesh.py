"""Close the mirrored linesplan loft mesh."""

from __future__ import annotations

from typing import TypeAlias

from loft_polylines import MIRRORED_STATION_MESH, MIRRORED_STATION_NODES, TOLERANCE

from cady import Mesh3

Point3: TypeAlias = tuple[float, float, float]
Face: TypeAlias = tuple[int, ...]
Edge: TypeAlias = tuple[int, int]

OPEN_MESH = MIRRORED_STATION_MESH

width = len(MIRRORED_STATION_NODES[0])
faces: list[Face] = list(OPEN_MESH.faces)
edges: set[Edge] = {(min(edge), max(edge)) for edge in OPEN_MESH.edges}

for row_index in range(len(MIRRORED_STATION_NODES) - 1):
    start = row_index * width
    next_start = (row_index + 1) * width
    faces.append((start, start + width - 1, next_start + width - 1, next_start))

for row_index in range(len(MIRRORED_STATION_NODES)):
    start = row_index * width
    end = start + width - 1
    edges.add((min(start, end), max(start, end)))

index_by_point: dict[tuple[int, int, int], int] = {}
vertices: list[Point3] = []
remap: list[int] = []

for x, y, z in OPEN_MESH.vertices:
    if abs(y) <= TOLERANCE:
        y = 0.0
    key = (round(x / TOLERANCE), round(y / TOLERANCE), round(z / TOLERANCE))
    if key not in index_by_point:
        index_by_point[key] = len(vertices)
        vertices.append((x, y, z))
    remap.append(index_by_point[key])

welded_faces: list[Face] = []
for face in faces:
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
    if len(unique) >= 3:
        welded_faces.append(tuple(unique))

welded_edges: set[Edge] = set()
for a, b in edges:
    start, end = remap[a], remap[b]
    if start != end:
        welded_edges.add((min(start, end), max(start, end)))

_WELDED_MESH = Mesh3(tuple(vertices), tuple(welded_faces), tuple(sorted(welded_edges)))
CLOSED_MESH = _WELDED_MESH.close_boundary(tolerance=TOLERANCE)
closed_mesh = CLOSED_MESH


if __name__ == "__main__":
    CLOSED_MESH.view(title="closed mirrored linesplan mesh")
