from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, cast

from cady.domain.base import Shape3D
from cady.domain.vec import Vec3
from cady.errors import SceneError
from cady.ops.tessellate import Triangle3


class ArrayMeshLike(Protocol):
    triangles: Sequence[Sequence[Sequence[float]]]


def triangles_to_array_mesh(triangles: Iterable[Triangle3]) -> object:
    from cady.numeric import ArrayMesh3
    from cady.numeric.validation import as_faces, as_points3

    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    index: dict[tuple[float, float, float], int] = {}
    for triangle in triangles:
        face: list[int] = []
        for point in triangle:
            key = point.tuple()
            existing = index.get(key)
            if existing is None:
                existing = len(vertices)
                index[key] = existing
                vertices.append(key)
            face.append(existing)
        faces.append((face[0], face[1], face[2]))
    return ArrayMesh3(as_points3(vertices, name="vertices"), as_faces(faces, name="faces"))


def array_mesh_to_triangles(mesh: ArrayMeshLike) -> list[Triangle3]:
    return [
        (
            Vec3(float(triangle[0][0]), float(triangle[0][1]), float(triangle[0][2])),
            Vec3(float(triangle[1][0]), float(triangle[1][1]), float(triangle[1][2])),
            Vec3(float(triangle[2][0]), float(triangle[2][1]), float(triangle[2][2])),
        )
        for triangle in mesh.triangles
    ]


@dataclass(slots=True)
class StlMesh:
    tolerance: float = 1e-3
    solids: list[Shape3D] = field(default_factory=list[Shape3D])
    triangles: list[Triangle3] = field(default_factory=list[Triangle3])
    array_meshes: list[object] = field(default_factory=list[object])

    def __post_init__(self) -> None:
        if self.tolerance <= 0:
            raise SceneError("STL tolerance must be positive")

    def add(self, *solids: Shape3D) -> StlMesh:
        for solid in solids:
            if not isinstance(cast(object, solid), Shape3D):
                raise SceneError("StlMesh accepts Shape3D values only")
            self.solids.append(solid)
            mesh = cast(ArrayMeshLike, solid.to_array(tolerance=self.tolerance))
            self.array_meshes.append(mesh)
            self.triangles.extend(array_mesh_to_triangles(mesh))
        return self

    def write(self, path: str | Path, ascii: bool = False) -> StlMesh:
        if ascii:
            from cady.files.stl.ascii import write_ascii_stl

            write_ascii_stl(self.triangles, Path(path))
        else:
            from cady.files.stl.binary import write_binary_stl

            write_binary_stl(self.triangles, Path(path))
        return self
