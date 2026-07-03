"""View the closed linesplan mesh built by main.py."""

from __future__ import annotations

from main import CLOSE_ERROR, CLOSED_MESH, COMBINED_MESH

OPEN_MESH = COMBINED_MESH
closed_mesh = CLOSED_MESH


if __name__ == "__main__":
    if CLOSED_MESH is None:
        raise SystemExit(f"could not close linesplan mesh: {CLOSE_ERROR}")
    CLOSED_MESH.view(title="closed linesplan mesh")
