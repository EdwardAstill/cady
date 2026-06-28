"""Light definitions for backend-independent scene descriptions."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import TypeAlias

from cady.product.material import Color, rgb
from cady.view.errors import ViewError

Point3: TypeAlias = tuple[float, float, float]


def _finite_point3(value: object, *, name: str) -> Point3:
    try:
        raw = tuple(float(component) for component in value)  # type: ignore[reportUnknownVariableType]
    except TypeError as exc:
        raise ViewError(f"{name} must be a finite 3D coordinate") from exc
    if len(raw) != 3 or any(not isfinite(component) for component in raw):
        raise ViewError(f"{name} must be a finite 3D coordinate")
    return raw


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

    direction: Point3 = (0.0, 0.0, -1.0)

    def __post_init__(self) -> None:
        Light.__post_init__(self)
        direction = _finite_point3(self.direction, name="direction")
        if direction == (0.0, 0.0, 0.0):
            raise ViewError("directional light direction must be non-zero")
        object.__setattr__(self, "direction", direction)


@dataclass(frozen=True, slots=True)
class PointLight(Light):
    """Light emitted from a position, optionally with a finite range."""

    position: Point3 = (0.0, 0.0, 0.0)
    range: float | None = None

    def __post_init__(self) -> None:
        Light.__post_init__(self)
        object.__setattr__(self, "position", _finite_point3(self.position, name="position"))
        if self.range is not None and (not isfinite(self.range) or self.range <= 0.0):
            raise ViewError("point light range must be positive when provided")


__all__ = ["AmbientLight", "DirectionalLight", "Light", "PointLight"]
