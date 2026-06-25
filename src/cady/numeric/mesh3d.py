from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Self

import numpy as np

from cady.errors import GeometryError
from cady.numeric.bounds import bounds3
from cady.numeric.transform import Transform3
from cady.numeric.types import EdgeArray, FaceArray, PointArray3
from cady.numeric.validation import as_edges, as_faces, as_points3


@dataclass(frozen=True, slots=True)
class ArrayPolyline3:
    vertices: PointArray3

    def __post_init__(self) -> None:
        vertices = as_points3(self.vertices, name="vertices")
        if len(vertices) == 0:
            raise ValueError("vertices must contain at least one point")
        object.__setattr__(self, "vertices", vertices)

    def bounds(self) -> tuple[PointArray3, PointArray3]:
        return bounds3(self.vertices, name="vertices")

    def transformed(self, transform: Transform3) -> Self:
        return type(self)(transform.apply_points(self.vertices))


@dataclass(frozen=True, slots=True)
class ArrayMesh3:
    vertices: PointArray3
    faces: FaceArray
    edges: EdgeArray = field(
        default_factory=lambda: np.empty((0, 2), dtype=np.int64)
    )

    def __post_init__(self) -> None:
        vertices = as_points3(self.vertices, name="vertices")
        faces = as_faces(self.faces, name="faces")
        edges = as_edges(self.edges, name="edges")
        if len(faces) > 0:
            if np.min(faces) < 0:
                raise ValueError("faces must not contain negative indices")
            if np.max(faces) >= len(vertices):
                raise ValueError("faces reference vertices outside the vertex array")
        if len(edges) > 0:
            if np.min(edges) < 0:
                raise ValueError("edges must not contain negative indices")
            if np.max(edges) >= len(vertices):
                raise ValueError("edges reference vertices outside the vertex array")
        object.__setattr__(self, "vertices", vertices)
        object.__setattr__(self, "faces", faces)
        object.__setattr__(self, "edges", edges)

    @property
    def triangles(self) -> PointArray3:
        return self.vertices[self.faces]

    @property
    def boundary(self) -> ArrayPolyline3:
        if len(self.faces) == 0:
            raise GeometryError("mesh has no faces; boundary is undefined")
        loops = self.boundary_loops
        if not loops:
            raise GeometryError("mesh is closed; no boundary")
        if len(loops) != 1:
            raise GeometryError(
                f"mesh has {len(loops)} boundary loops; boundary requires exactly one"
            )
        return loops[0]

    @property
    def boundary_loops(self) -> tuple[ArrayPolyline3, ...]:
        if len(self.faces) == 0:
            raise GeometryError("mesh has no faces; boundary is undefined")
        return tuple(
            _polyline_from_loop(self.vertices, loop)
            for loop in _boundary_loops(_boundary_halfedges(self.faces))
        )

    def bounds(self) -> tuple[PointArray3, PointArray3]:
        return bounds3(self.vertices, name="vertices")

    def transformed(self, transform: Transform3) -> Self:
        return type(self)(transform.apply_points(self.vertices), self.faces, self.edges)

    def mirror(self, plane_origin: object, plane_normal: object) -> Self:
        return type(self)(
            Transform3.mirror(plane_origin, plane_normal).apply_points(self.vertices),
            _reverse_face_winding(self.faces),
            self.edges,
        )

    @classmethod
    def merged(cls, meshes: Iterable[ArrayMesh3]) -> ArrayMesh3:
        mesh_tuple = tuple(meshes)
        if len(mesh_tuple) == 0:
            return cls(
                np.empty((0, 3), dtype=np.float64),
                np.empty((0, 3), dtype=np.int64),
                np.empty((0, 2), dtype=np.int64),
            )

        vertices: list[PointArray3] = []
        faces: list[FaceArray] = []
        edges: list[EdgeArray] = []
        vertex_offset = 0
        for mesh in mesh_tuple:
            vertices.append(mesh.vertices)
            if len(mesh.faces) > 0:
                faces.append(mesh.faces + vertex_offset)
            if len(mesh.edges) > 0:
                edges.append(mesh.edges + vertex_offset)
            vertex_offset += len(mesh.vertices)

        return cls(
            np.vstack(vertices).astype(np.float64, copy=False),
            _stack_indices(faces, width=3),
            _stack_indices(edges, width=2),
        )


def _stack_indices(arrays: list[np.ndarray], *, width: int) -> np.ndarray:
    if not arrays:
        return np.empty((0, width), dtype=np.int64)
    return np.vstack(arrays).astype(np.int64, copy=False)


def _boundary_halfedges(faces: FaceArray) -> list[tuple[int, int]]:
    occurrences: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for face in faces:
        indices = [int(face[0]), int(face[1]), int(face[2])]
        for start, end in zip(indices, indices[1:] + indices[:1], strict=True):
            occurrences[(min(start, end), max(start, end))].append((start, end))

    if any(len(edge_occurrences) > 2 for edge_occurrences in occurrences.values()):
        raise GeometryError("mesh boundary is undefined for non-manifold edges")

    return sorted(
        edge_occurrences[0]
        for edge_occurrences in occurrences.values()
        if len(edge_occurrences) == 1
    )


def _boundary_loops(halfedges: list[tuple[int, int]]) -> list[list[int]]:
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


def _polyline_from_loop(vertices: PointArray3, loop: list[int]) -> ArrayPolyline3:
    loop_vertices = vertices[loop + [loop[0]]]
    return ArrayPolyline3(loop_vertices.astype(np.float64, copy=False))


def _reverse_face_winding(faces: FaceArray) -> FaceArray:
    if len(faces) == 0:
        return faces.copy()
    return faces[:, [0, 2, 1]].astype(np.int64, copy=False)
