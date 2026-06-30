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


@dataclass(frozen=True, slots=True)
class LocalAxesOverlay:
    """Local X/Y/Z axes marker for scene views."""

    x_color: Color = (0.9, 0.05, 0.05)
    y_color: Color = (0.05, 0.62, 0.18)
    z_color: Color = (0.1, 0.28, 0.95)
    visible: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "x_color", rgb(self.x_color, name="local x-axis color"))
        object.__setattr__(self, "y_color", rgb(self.y_color, name="local y-axis color"))
        object.__setattr__(self, "z_color", rgb(self.z_color, name="local z-axis color"))


SceneOverlay: TypeAlias = ScaleBarOverlay | LocalAxesOverlay


__all__ = ["LocalAxesOverlay", "ScaleBarOverlay", "SceneOverlay"]
