"""Light definitions for backend-independent scene descriptions."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from cady.product.material import Color, rgb
from cady.view.camera import Vec3Like, vec3
from cady.view.errors import ViewError


@dataclass(frozen=True, slots=True)
class Light:
    """Base light with validated intensity and RGB color."""

    intensity: float = 1.0
    color: Color = (1.0, 1.0, 1.0)

    def __post_init__(self) -> None:
        if not isfinite(self.intensity) or self.intensity < 0.0:
            raise ViewError("light intensity must be a non-negative finite value")
        object.__setattr__(self, "color", rgb(self.color, name="light color"))


@dataclass(frozen=True, slots=True)
class AmbientLight(Light):
    """Uniform scene lighting with no direction."""

    pass


@dataclass(frozen=True, slots=True)
class DirectionalLight(Light):
    """Light emitted from infinitely far away along a direction."""

    direction: Vec3Like = (0.0, 0.0, -1.0)

    def __post_init__(self) -> None:
        Light.__post_init__(self)
        direction = vec3(self.direction, name="direction")
        if direction == (0.0, 0.0, 0.0):
            raise ViewError("directional light direction must be non-zero")
        object.__setattr__(self, "direction", direction)


@dataclass(frozen=True, slots=True)
class PointLight(Light):
    """Light emitted from a position, optionally with a finite range."""

    position: Vec3Like = (0.0, 0.0, 0.0)
    range: float | None = None

    def __post_init__(self) -> None:
        Light.__post_init__(self)
        object.__setattr__(self, "position", vec3(self.position, name="position"))
        if self.range is not None and (not isfinite(self.range) or self.range <= 0.0):
            raise ViewError("point light range must be positive when provided")


__all__ = ["AmbientLight", "DirectionalLight", "Light", "PointLight"]
