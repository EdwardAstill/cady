from __future__ import annotations

from pathlib import Path

from cady.domain.drawing import DxfDrawing
from cady.domain.model import Drawing2D, Model
from cady.files.dxf.reader import (
    Dxf3DImportResult,
    DxfSkippedEntity,
    parse_dxf,
    parse_dxf_3d,
    read_3d,
    read_dxf,
    read_mesh,
)
from cady.files.dxf.sections import render_dxf, write_dxf


def _as_dxf_drawing(drawing: Drawing2D | DxfDrawing) -> DxfDrawing:
    if isinstance(drawing, Drawing2D):
        return drawing.to_dxf_drawing()
    return drawing


def render_drawing(drawing: Drawing2D | DxfDrawing, *, tolerance: float = 1e-3) -> str:
    return render_dxf(_as_dxf_drawing(drawing), tolerance=tolerance)


def read_drawing(path: str | Path) -> DxfDrawing:
    return read_dxf(path)


def write_drawing(
    drawing: Drawing2D | DxfDrawing,
    path: str | Path,
    *,
    tolerance: float = 1e-3,
) -> Drawing2D | DxfDrawing:
    write_dxf(_as_dxf_drawing(drawing), Path(path), tolerance=tolerance)
    return drawing


def write_model(model: Model, path: str | Path, *, tolerance: float = 1e-3) -> Model:
    return model.write_dxf(path, tolerance=tolerance)


__all__ = [
    "parse_dxf",
    "parse_dxf_3d",
    "Dxf3DImportResult",
    "DxfSkippedEntity",
    "read_drawing",
    "read_dxf",
    "read_3d",
    "read_mesh",
    "render_drawing",
    "render_dxf",
    "write_drawing",
    "write_dxf",
    "write_model",
]
