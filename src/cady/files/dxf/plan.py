from __future__ import annotations

from dataclasses import dataclass

from cady.domain.drawing import DimStyle, DxfDrawing, Layer
from cady.files.dxf.blocks import dimension_block_names


@dataclass(frozen=True)
class DxfRenderPlan:
    layers: tuple[Layer, ...]
    dimension_block_names: tuple[str, ...]
    uses_dimstyle: bool
    dimstyles: tuple[DimStyle, ...]
    referenced_dimstyles: frozenset[str]


def make_render_plan(drawing: DxfDrawing) -> DxfRenderPlan:
    referenced = frozenset(
        dim.dimstyle for dim in drawing.dimensions
    )
    return DxfRenderPlan(
        layers=tuple(drawing.layers.values()),
        dimension_block_names=dimension_block_names(drawing),
        uses_dimstyle=bool(drawing.dimensions),
        dimstyles=drawing.dimstyles,
        referenced_dimstyles=referenced,
    )
