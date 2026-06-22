from __future__ import annotations

from pathlib import Path

from cady.errors import WriteError
from cady.ops.tessellate import Triangle3, normal_for_triangle


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
