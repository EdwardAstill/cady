"""STL writers for semantic meshes and mesh-coercible CAD targets."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import TypeAlias

from cady.errors import WriteError
from cady.files.utils import mesh_from_target
from cady.geometry import Mesh3
from cady.operations.coordinates import cross3, normalised3, sub3

Point3: TypeAlias = tuple[float, float, float]
Triangle3 = tuple[Point3, Point3, Point3]


def _f(value: float) -> str:
    return f"{value:.8g}"


def write_ascii_stl(triangles: list[Triangle3], path: Path) -> None:
    """Write triangles to an ASCII STL file."""
    if not triangles:
        raise WriteError("cannot write empty STL mesh")
    lines = ["solid cady"]
    for tri in triangles:
        normal = normal_for_triangle(tri)
        lines.append(f"  facet normal {_f(normal[0])} {_f(normal[1])} {_f(normal[2])}")
        lines.append("    outer loop")
        for point in tri:
            lines.append(f"      vertex {_f(point[0])} {_f(point[1])} {_f(point[2])}")
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append("endsolid")
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def normal_for_triangle(tri: Triangle3) -> Point3:
    """Return a unit triangle normal, or the zero vector for degenerate faces."""
    normal = cross3(sub3(tri[1], tri[0]), sub3(tri[2], tri[0]))
    try:
        return normalised3(normal)
    except ValueError:
        return (0.0, 0.0, 0.0)


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
                normal[0],
                normal[1],
                normal[2],
                tri[0][0],
                tri[0][1],
                tri[0][2],
                tri[1][0],
                tri[1][1],
                tri[1][2],
                tri[2][0],
                tri[2][1],
                tri[2][2],
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
    triangles = list(_triangles(mesh, tolerance=tolerance))
    output = Path(path)
    if ascii:
        write_ascii_stl(triangles, output)
    else:
        write_binary_stl(triangles, output)
    return target


def _mesh_from_target(target: object, *, tolerance: float) -> Mesh3:
    return mesh_from_target(target, tolerance=tolerance)


def _triangles(mesh: Mesh3, *, tolerance: float) -> tuple[Triangle3, ...]:
    return tuple(
        (mesh.vertices[a], mesh.vertices[b], mesh.vertices[c])
        for a, b, c in mesh.triangulated_faces(tolerance=tolerance)
    )


__all__ = ["write", "write_ascii_stl", "write_binary_stl"]
