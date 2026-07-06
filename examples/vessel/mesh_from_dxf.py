"""Build and view a vessel mesh from a DXF linesplan."""

from __future__ import annotations

from pathlib import Path

from cady.files import stl
from cady.vessels import Linesplan

ROOT = Path(__file__).resolve().parents[2]
DXF_FILE = ROOT / "examples" / "files" / "3d_lp.dxf"
STL_FILE = ROOT / "examples" / "files" / "created" / "mesh_from_dxf.stl"
# DXF_FILE = ROOT / "examples" / "files" / "linesplan_9m.dxf"


def main() -> None:
    linesplan = Linesplan.from_dxf(DXF_FILE)
    mesh = linesplan.to_mesh()
    STL_FILE.parent.mkdir(parents=True, exist_ok=True)
    stl.write(mesh, STL_FILE, tolerance=1e-3)
    linesplan.view(title="cleaned connected station lines")
    mesh.view(title="linesplan mesh")


if __name__ == "__main__":
    main()
