"""Build and view a closed linesplan mesh from DXF."""

from __future__ import annotations

from pathlib import Path

from cady import Mesh3
from cady.vessels import Linesplan

ROOT = Path(__file__).resolve().parents[2]
LINESPLAN_DXF = ROOT / "examples" / "files" / "linesplan_9m.dxf"


def build_mesh(path: str | Path = LINESPLAN_DXF) -> Mesh3:
    return Linesplan.from_dxf(path).to_mesh()


def main() -> None:
    mesh = build_mesh()
    print(
        "linesplan mesh: "
        f"{len(mesh.vertices)} vertices, {len(mesh.edges)} edges, {len(mesh.faces)} faces"
    )
    mesh.view(title="linesplan mesh from DXF")


if __name__ == "__main__":
    main()
