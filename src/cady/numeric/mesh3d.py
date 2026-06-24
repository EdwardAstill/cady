from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Self

import numpy as np

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


def _reverse_face_winding(faces: FaceArray) -> FaceArray:
    if len(faces) == 0:
        return faces.copy()
    return faces[:, [0, 2, 1]].astype(np.int64, copy=False)
