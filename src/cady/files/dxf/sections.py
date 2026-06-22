from __future__ import annotations

from pathlib import Path

from cady.domain.drawing import DxfDrawing
from cady.files.dxf.document import render_document


def render_dxf(drawing: DxfDrawing) -> str:
    return render_document(drawing)


def write_dxf(drawing: DxfDrawing, path: Path) -> None:
    path.write_text(render_dxf(drawing), encoding="ascii")
