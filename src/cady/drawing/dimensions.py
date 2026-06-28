"""Dimension entities and style records for 2D drawings."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TypeAlias

from cady.drawing._geometry import Bounds2, Point2, points_bounds


def format_measurement(value: float) -> str:
    """Format a numeric measurement without trailing zero noise."""
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _distance(a: Point2, b: Point2) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


@dataclass(frozen=True, slots=True)
class DimStyle:
    """Shared styling values for generated dimension annotations."""

    name: str = "Standard"
    text_height: float = 0.18
    arrow_size: float = 0.18
    decimal_places: int = 4
    extension_offset: float = 0.0625
    extension_extend: float = 0.18
    text_gap: float = 0.09

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("dimstyle name must be non-empty")
        if self.decimal_places < 0:
            raise ValueError("dimstyle decimal_places must be non-negative")
        for field_name in (
            "text_height",
            "arrow_size",
            "extension_offset",
            "extension_extend",
            "text_gap",
        ):
            if getattr(self, field_name) <= 0:
                raise ValueError(f"dimstyle {field_name} must be positive")


@dataclass(frozen=True, slots=True)
class LinearDimension2:
    """Horizontal or vertical linear measurement between two points."""

    p1: Point2
    p2: Point2
    offset: float
    layer: str = "DIMENSIONS"
    text: str | None = None
    text_height: float = 0.025
    dim_style: str = "Standard"

    def __post_init__(self) -> None:
        p1 = self.p1
        p2 = self.p2
        if p1 == p2:
            raise ValueError("dimension points must differ")
        if p1[0] != p2[0] and p1[1] != p2[1]:
            raise ValueError("linear dimensions require horizontal or vertical points")
        _validate_common(self.layer, self.text_height, self.dim_style)
        object.__setattr__(self, "p1", p1)
        object.__setattr__(self, "p2", p2)
        object.__setattr__(self, "offset", float(self.offset))
        object.__setattr__(self, "text_height", float(self.text_height))
        if self.text is None:
            object.__setattr__(self, "text", format_measurement(_distance(p1, p2)))

    def bounds(self) -> Bounds2:
        if self.p1[1] == self.p2[1]:
            shifted = (
                (self.p1[0], self.p1[1] + self.offset),
                (self.p2[0], self.p2[1] + self.offset),
            )
        else:
            shifted = (
                (self.p1[0] + self.offset, self.p1[1]),
                (self.p2[0] + self.offset, self.p2[1]),
            )
        return points_bounds((*self._points(), *shifted), name="linear dimension points")

    def _points(self) -> tuple[Point2, Point2]:
        return self.p1, self.p2


@dataclass(frozen=True, slots=True)
class AlignedDimension2:
    """Measurement between two points along their connecting direction."""

    p1: Point2
    p2: Point2
    offset: float
    layer: str = "DIMENSIONS"
    text: str | None = None
    text_height: float = 0.025
    dim_style: str = "Standard"

    def __post_init__(self) -> None:
        p1 = self.p1
        p2 = self.p2
        if p1 == p2:
            raise ValueError("dimension points must differ")
        _validate_common(self.layer, self.text_height, self.dim_style)
        object.__setattr__(self, "p1", p1)
        object.__setattr__(self, "p2", p2)
        object.__setattr__(self, "offset", float(self.offset))
        object.__setattr__(self, "text_height", float(self.text_height))
        if self.text is None:
            object.__setattr__(self, "text", format_measurement(_distance(p1, p2)))

    def bounds(self) -> Bounds2:
        dx = self.p2[0] - self.p1[0]
        dy = self.p2[1] - self.p1[1]
        length = math.hypot(dx, dy)
        nx = -dy / length
        ny = dx / length
        shifted = (
            (self.p1[0] + nx * self.offset, self.p1[1] + ny * self.offset),
            (self.p2[0] + nx * self.offset, self.p2[1] + ny * self.offset),
        )
        return points_bounds((self.p1, self.p2, *shifted), name="aligned dimension points")


@dataclass(frozen=True, slots=True)
class RadiusDimension2:
    """Radial measurement for a circular feature."""

    center: Point2
    radius: float
    angle: float = 0.0
    layer: str = "DIMENSIONS"
    text: str | None = None
    text_height: float = 0.025
    dim_style: str = "Standard"

    def __post_init__(self) -> None:
        if self.radius <= 0:
            raise ValueError("dimension radius must be positive")
        _validate_common(self.layer, self.text_height, self.dim_style)
        center = self.center
        object.__setattr__(self, "center", center)
        object.__setattr__(self, "radius", float(self.radius))
        object.__setattr__(self, "angle", float(self.angle))
        object.__setattr__(self, "text_height", float(self.text_height))
        if self.text is None:
            object.__setattr__(self, "text", f"R{format_measurement(float(self.radius))}")

    @property
    def end(self) -> Point2:
        """Return the leader endpoint at the current angle."""
        return (
            self.center[0] + self.radius * math.cos(self.angle),
            self.center[1] + self.radius * math.sin(self.angle),
        )

    def bounds(self) -> Bounds2:
        return points_bounds((self.center, self.end), name="radius dimension points")


@dataclass(frozen=True, slots=True)
class DiameterDimension2:
    """Diameter measurement for a circular feature."""

    center: Point2
    radius: float
    angle: float = 0.0
    layer: str = "DIMENSIONS"
    text: str | None = None
    text_height: float = 0.025
    dim_style: str = "Standard"

    def __post_init__(self) -> None:
        if self.radius <= 0:
            raise ValueError("dimension radius must be positive")
        _validate_common(self.layer, self.text_height, self.dim_style)
        center = self.center
        object.__setattr__(self, "center", center)
        object.__setattr__(self, "radius", float(self.radius))
        object.__setattr__(self, "angle", float(self.angle))
        object.__setattr__(self, "text_height", float(self.text_height))
        if self.text is None:
            object.__setattr__(self, "text", f"DIA {format_measurement(float(self.radius) * 2)}")

    @property
    def p1(self) -> Point2:
        """Return the first endpoint of the measured diameter."""
        return (
            self.center[0] - self.radius * math.cos(self.angle),
            self.center[1] - self.radius * math.sin(self.angle),
        )

    @property
    def p2(self) -> Point2:
        """Return the second endpoint of the measured diameter."""
        return (
            self.center[0] + self.radius * math.cos(self.angle),
            self.center[1] + self.radius * math.sin(self.angle),
        )

    def bounds(self) -> Bounds2:
        return points_bounds((self.p1, self.p2), name="diameter dimension points")


@dataclass(frozen=True, slots=True)
class AngularDimension2:
    """Angular measurement between two rays from a shared centre."""

    center: Point2
    p1: Point2
    p2: Point2
    distance: float
    layer: str = "DIMENSIONS"
    text: str | None = None
    text_height: float = 0.025
    dim_style: str = "Standard"

    def __post_init__(self) -> None:
        center = self.center
        p1 = self.p1
        p2 = self.p2
        if self.distance <= 0:
            raise ValueError("angular dimension distance must be positive")
        if center in (p1, p2):
            raise ValueError("angular dimension rays must be non-degenerate")
        _validate_common(self.layer, self.text_height, self.dim_style)
        object.__setattr__(self, "center", center)
        object.__setattr__(self, "p1", p1)
        object.__setattr__(self, "p2", p2)
        object.__setattr__(self, "distance", float(self.distance))
        object.__setattr__(self, "text_height", float(self.text_height))
        if self.text is None:
            object.__setattr__(self, "text", format_measurement(self.measurement_degrees()))

    def measurement_degrees(self) -> float:
        """Return the included angle in degrees."""
        v1 = (self.p1[0] - self.center[0], self.p1[1] - self.center[1])
        v2 = (self.p2[0] - self.center[0], self.p2[1] - self.center[1])
        mag1 = math.hypot(*v1)
        mag2 = math.hypot(*v2)
        cos_a = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (mag1 * mag2)))
        return math.degrees(math.acos(cos_a))

    def bounds(self) -> Bounds2:
        return points_bounds((self.center, self.p1, self.p2), name="angular dimension points")


Dimension2: TypeAlias = (
    LinearDimension2
    | AlignedDimension2
    | RadiusDimension2
    | DiameterDimension2
    | AngularDimension2
)


def _validate_common(layer: str, text_height: float, dim_style: str) -> None:
    if not layer:
        raise ValueError("dimension layer must be non-empty")
    if text_height <= 0:
        raise ValueError("dimension text height must be positive")
    if not dim_style:
        raise ValueError("dimension style must be non-empty")
