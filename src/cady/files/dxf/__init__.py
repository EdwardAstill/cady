from __future__ import annotations

from pathlib import Path

from cady.domain.drawing import DxfDrawing
from cady.domain.model import Drawing2D, Model
from cady.files.dxf.sections import render_dxf, write_dxf


def _as_dxf_drawing(drawing: Drawing2D | DxfDrawing) -> DxfDrawing:
    if isinstance(drawing, Drawing2D):
        return drawing.to_dxf_drawing()
    return drawing


def render_drawing(drawing: Drawing2D | DxfDrawing) -> str:
    return render_dxf(_as_dxf_drawing(drawing))


def write_drawing(drawing: Drawing2D | DxfDrawing, path: str | Path) -> Drawing2D | DxfDrawing:
    write_dxf(_as_dxf_drawing(drawing), Path(path))
    return drawing


def write_model(model: Model, path: str | Path) -> Model:
    return model.write_dxf(path)


__all__ = ["render_drawing", "render_dxf", "write_drawing", "write_dxf", "write_model"]
