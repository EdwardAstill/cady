from __future__ import annotations

from pathlib import Path

from cady.domain.drawing import DxfDrawing
from cady.files.dxf.document import render_document


def render_dxf(drawing: DxfDrawing, *, tolerance: float = 1e-3) -> str:
    return render_document(drawing, tolerance=tolerance)


def write_dxf(drawing: DxfDrawing, path: Path, *, tolerance: float = 1e-3) -> None:
    path.write_text(render_dxf(drawing, tolerance=tolerance), encoding="ascii")
