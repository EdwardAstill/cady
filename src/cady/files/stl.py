"""STL writers for semantic meshes and mesh-coercible CAD targets."""

from __future__ import annotations

import struct
from pathlib import Path

from cady.errors import WriteError
from cady.files.utils import mesh_from_target
from cady.geometry import Mesh3
from cady.vec import Vec3

Triangle3 = tuple[Vec3, Vec3, Vec3]


def _f(value: float) -> str:
    return f"{value:.8g}"


def write_ascii_stl(triangles: list[Triangle3], path: Path) -> None:
    """Write triangles to an ASCII STL file."""
    if not triangles:
        raise WriteError("cannot write empty STL mesh")
    lines = ["solid cady"]
    for tri in triangles:
        normal = normal_for_triangle(tri)
        lines.append(f"  facet normal {_f(normal.x)} {_f(normal.y)} {_f(normal.z)}")
        lines.append("    outer loop")
        for point in tri:
            lines.append(f"      vertex {_f(point.x)} {_f(point.y)} {_f(point.z)}")
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append("endsolid")
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def normal_for_triangle(tri: Triangle3) -> Vec3:
    """Return a unit triangle normal, or the zero vector for degenerate faces."""
    normal = (tri[1] - tri[0]).cross(tri[2] - tri[0])
    try:
        return normal.normalised()
    except ValueError:
        return Vec3(0.0, 0.0, 0.0)


def write_binary_stl(triangles: list[Triangle3], path: Path) -> None:
    """Write triangles to a binary STL file."""
    if not triangles:
        raise WriteError("cannot write empty STL mesh")
    with path.open("wb") as handle:
        handle.write(b"\0" * 80)
        handle.write(struct.pack("<I", len(triangles)))
        for tri in triangles:
            normal = normal_for_triangle(tri)
            values = [
                normal.x,
                normal.y,
                normal.z,
                tri[0].x,
                tri[0].y,
                tri[0].z,
                tri[1].x,
                tri[1].y,
                tri[1].z,
                tri[2].x,
                tri[2].y,
                tri[2].z,
            ]
            handle.write(struct.pack("<12fH", *values, 0))


def write(
    target: object,
    path: str | Path,
    *,
    ascii: bool = False,
    tolerance: float = 1e-3,
) -> object:
    """Coerce ``target`` to a mesh and write it as ASCII or binary STL."""
    mesh = _mesh_from_target(target, tolerance=tolerance)
    triangles = list(_triangles(mesh))
    output = Path(path)
    if ascii:
        write_ascii_stl(triangles, output)
    else:
        write_binary_stl(triangles, output)
    return target


def _mesh_from_target(target: object, *, tolerance: float) -> Mesh3:
    return mesh_from_target(target, tolerance=tolerance)


def _triangles(mesh: Mesh3) -> tuple[Triangle3, ...]:
    return tuple(
        (
            Vec3.from_xyz(mesh.vertices[a].tuple()),
            Vec3.from_xyz(mesh.vertices[b].tuple()),
            Vec3.from_xyz(mesh.vertices[c].tuple()),
        )
        for a, b, c in mesh.faces
    )


__all__ = ["write", "write_ascii_stl", "write_binary_stl"]
