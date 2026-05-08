from __future__ import annotations

import struct
from pathlib import Path

from cad.errors import WriteError
from cad.geom.tessellate import Triangle3, normal_for_triangle


def write_binary_stl(triangles: list[Triangle3], path: Path) -> None:
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
