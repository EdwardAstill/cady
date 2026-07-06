"""Build and view a vessel mesh from a DXF linesplan."""

from __future__ import annotations

from pathlib import Path

from cady.vessels import Linesplan

ROOT = Path(__file__).resolve().parents[2]
DXF_FILE = ROOT / "examples" / "files" / "3d_lp.dxf"
#DXF_FILE = ROOT / "examples" / "files" / "linesplan_9m.dxf"



def main():
    linesplan = Linesplan.from_dxf(DXF_FILE)
    mesh = linesplan.to_mesh()
    linesplan.view(title="cleaned connected station lines")
    mesh.view(title="linesplan mesh")


if __name__ == "__main__":
    main()
