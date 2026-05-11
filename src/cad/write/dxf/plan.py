from __future__ import annotations

from dataclasses import dataclass

from cad.scene.dxf import DxfDrawing, Layer
from cad.write.dxf.blocks import dimension_block_names


@dataclass(frozen=True)
class DxfRenderPlan:
    layers: tuple[Layer, ...]
    dimension_block_names: tuple[str, ...]
    uses_dimstyle: bool


def make_render_plan(drawing: DxfDrawing) -> DxfRenderPlan:
    return DxfRenderPlan(
        layers=tuple(drawing.layers.values()),
        dimension_block_names=dimension_block_names(drawing),
        uses_dimstyle=bool(drawing.dimensions),
    )
