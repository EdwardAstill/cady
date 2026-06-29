"""Mesh a linesplan by lofting longitudinal polylines.

Usage:
    PYTHONPATH=src .venv/bin/python examples/linesplan3/mesh_linesplan.py
"""

from __future__ import annotations

from linesplan import build_linespan
from loft import loft_polylines

if __name__ == "__main__":
    linespan = build_linespan()
    mesh = loft_polylines(linespan.polylines, station_count=48, section_count=16)
    print(f"mesh: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")
    mesh.view(title="Linesplan 3 — Lofted Mesh")
