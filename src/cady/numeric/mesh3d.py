from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Self

import numpy as np

from cady.numeric.bounds import bounds3
from cady.numeric.transform import Transform3
from cady.numeric.types import FaceArray, PointArray3
from cady.numeric.validation import as_faces, as_points3


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

    def __post_init__(self) -> None:
        vertices = as_points3(self.vertices, name="vertices")
        faces = as_faces(self.faces, name="faces")
        if len(faces) > 0:
            if np.min(faces) < 0:
                raise ValueError("faces must not contain negative indices")
            if np.max(faces) >= len(vertices):
                raise ValueError("faces reference vertices outside the vertex array")
        object.__setattr__(self, "vertices", vertices)
        object.__setattr__(self, "faces", faces)

    @property
    def triangles(self) -> PointArray3:
        return self.vertices[self.faces]

    def bounds(self) -> tuple[PointArray3, PointArray3]:
        return bounds3(self.vertices, name="vertices")

    def transformed(self, transform: Transform3) -> Self:
        return type(self)(transform.apply_points(self.vertices), self.faces)

    def visualise(self, *, tolerance: float = 1e-3) -> None:
        """Open an interactive 3D viewer for this mesh."""
        from cady.visualisation.vispy_viewer import vispy_view_mesh

        vispy_view_mesh(self)

    @classmethod
    def merged(cls, meshes: Iterable[ArrayMesh3]) -> ArrayMesh3:
        mesh_tuple = tuple(meshes)
        if len(mesh_tuple) == 0:
            return cls(
                np.empty((0, 3), dtype=np.float64),
                np.empty((0, 3), dtype=np.int64),
            )

        vertices: list[PointArray3] = []
        faces: list[FaceArray] = []
        vertex_offset = 0
        for mesh in mesh_tuple:
            vertices.append(mesh.vertices)
            faces.append(mesh.faces + vertex_offset)
            vertex_offset += len(mesh.vertices)

        return cls(
            np.vstack(vertices).astype(np.float64, copy=False),
            np.vstack(faces).astype(np.int64, copy=False),
        )
