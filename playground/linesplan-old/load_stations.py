"""Load the source station curves from the linesplan DXF.

This module is the input boundary for the example. It reads the DXF through
the public cady file facade, classifies the curve network, and returns only the
station lines needed by the downstream mesh-building processes.
"""

from __future__ import annotations

from pathlib import Path

from cady import Polyline3
from cady.errors import ReadError
from cady.files import dxf
from cady.operations.linesplan_meshing import classify_linesplan_curves

ROOT = Path(__file__).resolve().parents[2]
LINESPLAN_DXF = ROOT / "examples" / "inputs" / "linesplan_9m.dxf"


def load_station_polylines(
    path: str | Path = LINESPLAN_DXF,
    *,
    tolerance: float = 1e-3,
) -> tuple[Polyline3, ...]:
    """Read a DXF and return the classified station curves as polylines."""
    network = classify_linesplan_curves(dxf.read_curves(path), tolerance=tolerance)
    polylines = tuple(Polyline3(curve.vertices) for curve in network.sections)
    if not polylines:
        raise ReadError("DXF contained no station line geometry")
    return polylines
