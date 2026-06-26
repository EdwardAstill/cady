from __future__ import annotations

from dataclasses import dataclass, field
from typing import Self

import numpy as np

from cady.operations.bounds import bounds3
from cady.operations.transforms import Transform3
from cady.operations.types import EdgeArray, FaceArray, PointArray3
from cady.operations.validation import as_edges, as_faces, as_points3


@dataclass(frozen=True, slots=True)
class ArrayMesh3:
    vertices: PointArray3
    faces: FaceArray
    edges: EdgeArray = field(default_factory=lambda: np.empty((0, 2), dtype=np.int64))

    def __post_init__(self) -> None:
        vertices = as_points3(self.vertices, name="vertices")
        faces = as_faces(self.faces, name="faces")
        edges = as_edges(self.edges, name="edges")
        object.__setattr__(self, "vertices", vertices)
        object.__setattr__(self, "faces", faces)
        object.__setattr__(self, "edges", edges)

    def bounds(self) -> tuple[PointArray3, PointArray3]:
        return bounds3(self.vertices, name="vertices")

    @property
    def triangles(self) -> PointArray3:
        return self.vertices[self.faces]

    def transformed(self, transform: Transform3) -> Self:
        return type(self)(transform.apply_points(self.vertices), self.faces, self.edges)


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
