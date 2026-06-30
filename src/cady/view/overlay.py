"""Overlay values for backend-independent scene descriptions."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import TypeAlias

from cady.product.material import Color, rgb
from cady.view.errors import ViewError


@dataclass(frozen=True, slots=True)
class ScaleBarOverlay:
    """Screen-space scale bar for orthographic scene views."""

    color: Color = (0.05, 0.06, 0.07)
    min_pixels: float = 36.0
    max_pixels: float = 140.0
    visible: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "color", rgb(self.color, name="scale bar color"))
        if not isfinite(self.min_pixels) or self.min_pixels <= 0.0:
            raise ViewError("scale bar min_pixels must be positive")
        if not isfinite(self.max_pixels) or self.max_pixels <= 0.0:
            raise ViewError("scale bar max_pixels must be positive")
        if self.max_pixels < self.min_pixels:
            raise ViewError("scale bar max_pixels must be greater than or equal to min_pixels")


SceneOverlay: TypeAlias = ScaleBarOverlay


__all__ = ["ScaleBarOverlay", "SceneOverlay"]
