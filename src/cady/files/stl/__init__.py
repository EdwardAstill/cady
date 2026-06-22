from __future__ import annotations

from pathlib import Path

from cady.domain.mesh import StlMesh
from cady.domain.model import Model
from cady.files.stl.ascii import write_ascii_stl
from cady.files.stl.binary import write_binary_stl


def write_mesh(mesh: StlMesh, path: str | Path, *, ascii: bool = False) -> StlMesh:
    return mesh.write(Path(path), ascii=ascii)


def write_model(
    model: Model,
    path: str | Path,
    *,
    ascii: bool = False,
    tolerance: float = 1e-3,
) -> Model:
    return model.write_stl(path, ascii=ascii, tolerance=tolerance)


__all__ = ["write_ascii_stl", "write_binary_stl", "write_mesh", "write_model"]
