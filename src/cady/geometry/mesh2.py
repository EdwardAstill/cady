"""Semantic 2D triangle meshes with optional display edges."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from cady.vec import Vec2, promote2

if TYPE_CHECKING:
    from cady.operations.transforms import Transform2

FaceIndex = tuple[int, int, int]
EdgeIndex = tuple[int, int]


@dataclass(frozen=True, slots=True)
class Mesh2:
    """Indexed 2D triangle mesh used at numeric conversion boundaries."""

    vertices: tuple[Vec2, ...]
    faces: tuple[FaceIndex, ...]
    edges: tuple[EdgeIndex, ...] = ()

    def __post_init__(self) -> None:
        vertices = tuple(promote2(vertex) for vertex in self.vertices)
        faces = tuple(_face(face) for face in self.faces)
        edges = tuple(_edge(edge) for edge in self.edges)
        for face in faces:
            if min(face) < 0:
                raise ValueError("faces must not contain negative indices")
            if vertices and max(face) >= len(vertices):
                raise ValueError("faces reference vertices outside the vertex array")
            if not vertices:
                raise ValueError("empty meshes cannot contain faces")
        for edge in edges:
            if min(edge) < 0:
                raise ValueError("edges must not contain negative indices")
            if vertices and max(edge) >= len(vertices):
                raise ValueError("edges reference vertices outside the vertex array")
            if not vertices:
                raise ValueError("empty meshes cannot contain edges")
        object.__setattr__(self, "vertices", vertices)
        object.__setattr__(self, "faces", faces)
        object.__setattr__(self, "edges", edges)

    @classmethod
    def merged(cls, meshes: Iterable[Mesh2]) -> Mesh2:
        vertices: list[Vec2] = []
        faces: list[FaceIndex] = []
        edges: list[EdgeIndex] = []
        offset = 0
        for mesh in meshes:
            vertices.extend(mesh.vertices)
            faces.extend((a + offset, b + offset, c + offset) for a, b, c in mesh.faces)
            edges.extend((a + offset, b + offset) for a, b in mesh.edges)
            offset += len(mesh.vertices)
        return cls(tuple(vertices), tuple(faces), tuple(edges))

    @property
    def triangles(self) -> tuple[tuple[Vec2, Vec2, Vec2], ...]:
        return tuple(
            (self.vertices[a], self.vertices[b], self.vertices[c]) for a, b, c in self.faces
        )

    def to_array(self, *, tolerance: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        _validate_tolerance(tolerance)
        vertices = np.array([vertex.tuple() for vertex in self.vertices], dtype=np.float64)
        faces = np.array(self.faces, dtype=np.int64)
        edges = np.array(self.edges, dtype=np.int64)
        if len(vertices) == 0:
            vertices = np.empty((0, 2), dtype=np.float64)
        if len(faces) == 0:
            faces = np.empty((0, 3), dtype=np.int64)
        if len(edges) == 0:
            edges = np.empty((0, 2), dtype=np.int64)
        return vertices, faces, edges

    def transformed(self, transform: Transform2) -> Mesh2:
        array = transform.apply_points([vertex.tuple() for vertex in self.vertices])
        vertices = tuple(Vec2(float(x), float(y)) for x, y in array)
        return Mesh2(vertices, self.faces, self.edges)

    def bounds(self) -> tuple[Vec2, Vec2]:
        if not self.vertices:
            raise ValueError("cannot calculate bounds for an empty mesh")
        return (
            Vec2(
                min(vertex.x for vertex in self.vertices),
                min(vertex.y for vertex in self.vertices),
            ),
            Vec2(
                max(vertex.x for vertex in self.vertices),
                max(vertex.y for vertex in self.vertices),
            ),
        )


def _face(value: tuple[int, int, int]) -> FaceIndex:
    if len(value) != 3:
        raise ValueError("mesh faces must have exactly three indices")
    return (int(value[0]), int(value[1]), int(value[2]))


def _edge(value: tuple[int, int]) -> EdgeIndex:
    if len(value) != 2:
        raise ValueError("mesh edges must have exactly two indices")
    return (int(value[0]), int(value[1]))


def _validate_tolerance(tolerance: float) -> None:
    if float(tolerance) <= 0.0:
        raise ValueError("tolerance must be positive")
