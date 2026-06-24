from __future__ import annotations

from pathlib import Path

from cady.document import Document
from cady.errors import WriteError
from cady.files.stl.ascii import Triangle3, write_ascii_stl
from cady.files.stl.binary import write_binary_stl
from cady.geometry3d import Mesh3D
from cady.numeric.mesh3d import ArrayMesh3
from cady.vec import Vec3


def write(
    target: object,
    path: str | Path,
    *,
    ascii: bool = False,
    tolerance: float = 1e-3,
) -> object:
    mesh = _mesh_from_target(target, tolerance=tolerance)
    triangles = list(_triangles(mesh))
    output = Path(path)
    if ascii:
        write_ascii_stl(triangles, output)
    else:
        write_binary_stl(triangles, output)
    return target


def _mesh_from_target(target: object, *, tolerance: float) -> Mesh3D:
    if tolerance <= 0:
        raise WriteError("tolerance must be positive")
    if isinstance(target, Mesh3D):
        return target
    if isinstance(target, ArrayMesh3):
        return Mesh3D.from_array(target)
    if isinstance(target, Document):
        meshes: list[Mesh3D] = []
        for item in (*target.parts, *target.assemblies):
            meshes.append(_mesh_from_target(item.value, tolerance=tolerance))
        if not meshes:
            raise WriteError("document contains no meshable parts or assemblies")
        return Mesh3D.merged(meshes)
    to_mesh = getattr(target, "to_mesh", None)
    if callable(to_mesh):
        mesh = to_mesh(tolerance=tolerance)
        if isinstance(mesh, Mesh3D):
            return mesh
        if isinstance(mesh, ArrayMesh3):
            return Mesh3D.from_array(mesh)
    raise WriteError(f"{type(target).__name__} is not meshable")


def _triangles(mesh: Mesh3D) -> tuple[Triangle3, ...]:
    return tuple(
        (
            Vec3.from_xyz(mesh.vertices[a].tuple()),
            Vec3.from_xyz(mesh.vertices[b].tuple()),
            Vec3.from_xyz(mesh.vertices[c].tuple()),
        )
        for a, b, c in mesh.faces
    )


__all__ = ["write", "write_ascii_stl", "write_binary_stl"]
