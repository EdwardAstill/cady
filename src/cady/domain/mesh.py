from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Protocol, cast

from cady.domain.base import Shape3D
from cady.domain.vec import Vec3
from cady.errors import SceneError
from cady.ops.tessellate import Triangle3


class ArrayMeshLike(Protocol):
    triangles: Sequence[Sequence[Sequence[float]]]


def _bounds(points: tuple[Vec3, ...]) -> tuple[Vec3, Vec3]:
    return (
        Vec3(min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)),
        Vec3(max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)),
    )


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


@dataclass(frozen=True, slots=True)
class Face3D:
    vertices: tuple[Vec3, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "vertices", tuple(Vec3.from_xyz(p) for p in self.vertices))
        if len(self.vertices) < 3:
            raise ValueError("Face3D requires at least three vertices")

    def triangles(self) -> tuple[tuple[Vec3, Vec3, Vec3], ...]:
        first = self.vertices[0]
        return tuple(
            (first, self.vertices[index], self.vertices[index + 1])
            for index in range(1, len(self.vertices) - 1)
        )

    def bounds(self) -> tuple[Vec3, Vec3]:
        return _bounds(self.vertices)


@dataclass(frozen=True, slots=True)
class Polyline3D:
    vertices: tuple[Vec3, ...]
    closed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "vertices", tuple(Vec3.from_xyz(p) for p in self.vertices))
        object.__setattr__(self, "closed", bool(self.closed))
        if len(self.vertices) == 0:
            raise ValueError("Polyline3D requires at least one vertex")
        if self.closed and len(self.vertices) < 3:
            raise ValueError("closed Polyline3D requires at least three vertices")

    def bounds(self) -> tuple[Vec3, Vec3]:
        return _bounds(self.vertices)

    def _transform3(self, fn: Callable[[Vec3], Vec3]) -> Polyline3D:
        return replace(self, vertices=tuple(fn(vertex) for vertex in self.vertices))

    def to_array(self, *, tolerance: float = 1e-3) -> object:
        from cady.numeric import ArrayPolyline3
        from cady.numeric.validation import as_points3

        return ArrayPolyline3(
            as_points3(tuple(vertex.tuple() for vertex in self.vertices), name="vertices")
        )


@dataclass(frozen=True, slots=True)
class FacetedMesh(Shape3D):
    vertices: tuple[Vec3, ...]
    faces: tuple[tuple[int, int, int], ...]

    def __post_init__(self) -> None:
        vertices = tuple(Vec3.from_xyz(vertex) for vertex in self.vertices)
        faces = tuple(tuple(int(index) for index in face) for face in self.faces)
        if len(vertices) == 0:
            raise ValueError("FacetedMesh requires at least one vertex")
        if len(faces) == 0:
            raise ValueError("FacetedMesh requires at least one face")
        for face in faces:
            if len(face) != 3:
                raise ValueError("FacetedMesh faces must be triangles")
            for index in face:
                if index < 0 or index >= len(vertices):
                    raise ValueError("FacetedMesh face index out of range")
        object.__setattr__(self, "vertices", vertices)
        object.__setattr__(self, "faces", faces)

    @classmethod
    def from_faces(cls, faces: Iterable[Face3D]) -> FacetedMesh:
        vertices: list[Vec3] = []
        mesh_faces: list[tuple[int, int, int]] = []
        index_by_point: dict[tuple[float, float, float], int] = {}
        for face in faces:
            for triangle in face.triangles():
                triangle_indices: list[int] = []
                for vertex in triangle:
                    key = vertex.tuple()
                    index = index_by_point.get(key)
                    if index is None:
                        index = len(vertices)
                        index_by_point[key] = index
                        vertices.append(vertex)
                    triangle_indices.append(index)
                mesh_faces.append((triangle_indices[0], triangle_indices[1], triangle_indices[2]))
        return cls(tuple(vertices), tuple(mesh_faces))

    def bounds(self) -> tuple[Vec3, Vec3]:
        return _bounds(self.vertices)

    def _transform3(self, fn: Callable[[Vec3], Vec3]) -> Shape3D:
        return replace(self, vertices=tuple(fn(vertex) for vertex in self.vertices))

    def to_array(self, *, tolerance: float = 1e-3) -> object:
        from cady.numeric import ArrayMesh3
        from cady.numeric.validation import as_faces, as_points3

        return ArrayMesh3(
            as_points3(tuple(vertex.tuple() for vertex in self.vertices), name="vertices"),
            as_faces(self.faces, name="faces"),
        )

    @classmethod
    def merged(cls, meshes: Iterable[FacetedMesh]) -> FacetedMesh:
        vertices: list[Vec3] = []
        faces: list[tuple[int, int, int]] = []
        for mesh in meshes:
            offset = len(vertices)
            vertices.extend(mesh.vertices)
            faces.extend(
                (face[0] + offset, face[1] + offset, face[2] + offset)
                for face in mesh.faces
            )
        return cls(tuple(vertices), tuple(faces))


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
