from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from cad.errors import SceneError
from cad.geom.base import Shape3D
from cad.geom.tessellate import Triangle3, triangles_for_solid


@dataclass(slots=True)
class StlMesh:
    tolerance: float = 1e-3
    solids: list[Shape3D] = field(default_factory=list[Shape3D])
    triangles: list[Triangle3] = field(default_factory=list[Triangle3])

    def __post_init__(self) -> None:
        if self.tolerance <= 0:
            raise SceneError("STL tolerance must be positive")

    def add(self, *solids: Shape3D) -> StlMesh:
        for solid in solids:
            if not isinstance(cast(object, solid), Shape3D):
                raise SceneError("StlMesh accepts Shape3D values only")
            self.solids.append(solid)
            self.triangles.extend(triangles_for_solid(solid, tolerance=self.tolerance))
        return self

    def write(self, path: str | Path, ascii: bool = False) -> StlMesh:
        if ascii:
            from cad.write.stl.ascii import write_ascii_stl

            write_ascii_stl(self.triangles, Path(path))
        else:
            from cad.write.stl.binary import write_binary_stl

            write_binary_stl(self.triangles, Path(path))
        return self
