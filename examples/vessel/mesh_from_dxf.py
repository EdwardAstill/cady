"""Sketch the target vessel Linesplan API for meshing a DXF linesplan.

This example documents the intended public API before the playground
linesplan workflow is adopted into :mod:`cady.vessels`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from cady.geometry import Mesh3
from cady.vessels import Linesplan

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DXF = ROOT / "examples" / "files" / "linesplan_9m.dxf"


def mesh_from_dxf(path: str | Path = DEFAULT_DXF) -> Mesh3:
    linesplan = Linesplan.from_dxf(path)
    return linesplan.to_mesh()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a vessel mesh from cleaned DXF station lines.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_DXF,
        help="DXF linesplan to import.",
    )
    parser.add_argument(
        "--no-view",
        action="store_true",
        help="Print summaries without opening viewer windows.",
    )
    args = parser.parse_args()

    linesplan = Linesplan.from_dxf(args.input)
    mesh = linesplan.to_mesh()

    print(f"input: {args.input}")
    print(f"station lines: {len(linesplan.polylines)}")
    print(
        "mesh: "
        f"{len(mesh.vertices)} vertices, {len(mesh.faces)} faces, {len(mesh.edges)} edges"
    )

    if args.no_view:
        return

    linesplan.view(title="cleaned connected station lines")
    mesh.view(title="linesplan mesh")


if __name__ == "__main__":
    main()
