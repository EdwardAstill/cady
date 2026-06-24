from __future__ import annotations

from pathlib import Path

from cady.errors import WriteError
from cady.vec import Vec3

Triangle3 = tuple[Vec3, Vec3, Vec3]


def _f(value: float) -> str:
    return f"{value:.8g}"


def write_ascii_stl(triangles: list[Triangle3], path: Path) -> None:
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
    normal = (tri[1] - tri[0]).cross(tri[2] - tri[0])
    try:
        return normal.normalised()
    except ValueError:
        return Vec3(0.0, 0.0, 0.0)
