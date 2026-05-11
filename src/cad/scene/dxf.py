from __future__ import annotations

import math
from dataclasses import dataclass, field
from math import cos, sin
from pathlib import Path
from typing import Literal, cast

from cad.errors import SceneError
from cad.geom.base import Shape2D
from cad.geom.vec import Vec2, promote2

SUPPORTED_LINETYPES = {"CONTINUOUS", "HIDDEN", "CENTER"}


def _normalise_linetype(linetype: str) -> str:
    value = linetype.upper()
    if value not in SUPPORTED_LINETYPES:
        raise SceneError(f"unsupported DXF linetype: {linetype}")
    return value


@dataclass(slots=True)
class TextEntity:
    text: str
    at: Vec2
    height: float
    layer: str


DimensionKind = Literal["linear", "aligned", "radius", "diameter"]


def _format_measurement(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


@dataclass(slots=True)
class DimensionEntity:
    kind: DimensionKind
    a: Vec2
    b: Vec2
    offset: float
    layer: str
    text: str
    text_height: float


@dataclass(frozen=True, slots=True)
class AngularDimensionEntity:
    """3-point angular dimension (vertex + two ray endpoints)."""

    center: tuple[float, float]
    p1: tuple[float, float]
    p2: tuple[float, float]
    distance: float
    layer: str
    dimstyle: str = "PYSEAS"
    measurement_text: str = ""

    def __post_init__(self) -> None:
        if self.distance <= 0:
            raise ValueError("AngularDimensionEntity: distance must be positive")
        if self.measurement_text == "":
            v1 = (self.p1[0] - self.center[0], self.p1[1] - self.center[1])
            v2 = (self.p2[0] - self.center[0], self.p2[1] - self.center[1])
            mag1 = math.hypot(*v1)
            mag2 = math.hypot(*v2)
            if mag1 == 0 or mag2 == 0:
                raise ValueError("AngularDimensionEntity: rays must be non-degenerate")
            cos_a = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (mag1 * mag2)))
            angle_deg = math.degrees(math.acos(cos_a))
            object.__setattr__(self, "measurement_text", _format_measurement(angle_deg))


@dataclass(slots=True)
class HatchEntity:
    boundary: Shape2D
    layer: str
    pattern: str = "ANSI31"
    angle: float = 45.0
    scale: float = 1.0


@dataclass(slots=True)
class InsertEntity:
    name: str
    at: Vec2
    layer: str = "0"
    scale: float = 1.0
    rotation: float = 0.0


@dataclass(slots=True)
class Layer:
    name: str
    color: int = 7
    linetype: str = "CONTINUOUS"
    entities: list[Shape2D] = field(default_factory=list[Shape2D])
    hatches: list[HatchEntity] = field(default_factory=list[HatchEntity])

    def add(self, shape: Shape2D) -> Layer:
        if not isinstance(cast(object, shape), Shape2D):
            raise SceneError("DxfDrawing layers accept Shape2D values only")
        self.entities.append(shape)
        return self

    def hatch(
        self,
        boundary: Shape2D,
        *,
        pattern: str = "ANSI31",
        angle: float = 45.0,
        scale: float = 1.0,
    ) -> Layer:
        if not isinstance(cast(object, boundary), Shape2D):
            raise SceneError("DXF hatches require Shape2D boundaries")
        if not boundary.closed:
            raise SceneError("DXF hatch boundary must be closed")
        if pattern.upper() != "ANSI31":
            raise SceneError("only ANSI31 hatch pattern is supported")
        if scale <= 0:
            raise SceneError("hatch scale must be positive")
        self.hatches.append(HatchEntity(boundary, self.name, "ANSI31", float(angle), float(scale)))
        return self


@dataclass(slots=True)
class BlockDefinition:
    name: str
    base: Vec2 = field(default_factory=lambda: Vec2(0, 0))
    layers: dict[str, Layer] = field(default_factory=dict[str, Layer])
    texts: list[TextEntity] = field(default_factory=list[TextEntity])

    def __post_init__(self) -> None:
        if not self.name:
            raise SceneError("block name cannot be empty")
        object.__setattr__(self, "base", promote2(self.base))

    def layer(self, name: str, color: int = 7, linetype: str = "CONTINUOUS") -> Layer:
        if not name:
            raise SceneError("layer name cannot be empty")
        normalised_linetype = _normalise_linetype(linetype)
        existing = self.layers.get(name)
        if existing is not None:
            return existing
        layer = Layer(name, int(color), normalised_linetype)
        self.layers[name] = layer
        return layer

    def add_text(
        self,
        text: str,
        at: Vec2 | tuple[float, float],
        height: float,
        layer: str = "0",
    ) -> BlockDefinition:
        if height <= 0:
            raise SceneError("text height must be positive")
        self.layer(layer)
        self.texts.append(TextEntity(text, promote2(at), float(height), layer))
        return self


@dataclass(slots=True)
class DxfDrawing:
    layers: dict[str, Layer] = field(default_factory=dict[str, Layer])
    texts: list[TextEntity] = field(default_factory=list[TextEntity])
    blocks: dict[str, BlockDefinition] = field(default_factory=dict[str, BlockDefinition])
    inserts: list[InsertEntity] = field(default_factory=list[InsertEntity])
    dimensions: list[DimensionEntity | AngularDimensionEntity] = field(
        default_factory=list[DimensionEntity | AngularDimensionEntity]
    )

    @property
    def hatches(self) -> list[HatchEntity]:
        return [hatch for layer in self.layers.values() for hatch in layer.hatches]

    def layer(self, name: str, color: int = 7, linetype: str = "CONTINUOUS") -> Layer:
        if not name:
            raise SceneError("layer name cannot be empty")
        normalised_linetype = _normalise_linetype(linetype)
        existing = self.layers.get(name)
        if existing is not None:
            return existing
        layer = Layer(name, int(color), normalised_linetype)
        self.layers[name] = layer
        return layer

    def add_text(
        self,
        text: str,
        at: Vec2 | tuple[float, float],
        height: float,
        layer: str = "0",
    ) -> DxfDrawing:
        if height <= 0:
            raise SceneError("text height must be positive")
        self.layer(layer)
        self.texts.append(TextEntity(text, promote2(at), float(height), layer))
        return self

    def block(
        self,
        name: str,
        base: Vec2 | tuple[float, float] = (0, 0),
    ) -> BlockDefinition:
        if not name:
            raise SceneError("block name cannot be empty")
        if name in self.blocks:
            raise SceneError(f"duplicate block name: {name}")
        block = BlockDefinition(name, promote2(base))
        self.blocks[name] = block
        return block

    def insert(
        self,
        name: str,
        at: Vec2 | tuple[float, float],
        *,
        layer: str = "0",
        scale: float = 1.0,
        rotation: float = 0.0,
    ) -> DxfDrawing:
        if name not in self.blocks:
            raise SceneError(f"unknown block: {name}")
        if scale <= 0:
            raise SceneError("insert scale must be positive")
        self.layer(layer)
        self.inserts.append(InsertEntity(name, promote2(at), layer, float(scale), float(rotation)))
        return self

    def linear_dimension(
        self,
        a: Vec2 | tuple[float, float],
        b: Vec2 | tuple[float, float],
        *,
        offset: float,
        layer: str = "DIMENSIONS",
        text: str | None = None,
        text_height: float = 0.025,
    ) -> DxfDrawing:
        start = promote2(a)
        end = promote2(b)
        if start == end:
            raise SceneError("dimension points must differ")
        if start.x != end.x and start.y != end.y:
            raise SceneError("linear dimensions require horizontal or vertical points; use aligned")
        return self._dimension("linear", start, end, offset, layer, text, text_height)

    def aligned_dimension(
        self,
        a: Vec2 | tuple[float, float],
        b: Vec2 | tuple[float, float],
        *,
        offset: float,
        layer: str = "DIMENSIONS",
        text: str | None = None,
        text_height: float = 0.025,
    ) -> DxfDrawing:
        start = promote2(a)
        end = promote2(b)
        if start == end:
            raise SceneError("dimension points must differ")
        return self._dimension("aligned", start, end, offset, layer, text, text_height)

    def radius_dimension(
        self,
        centre: Vec2 | tuple[float, float],
        radius: float,
        *,
        angle: float = 0.0,
        layer: str = "DIMENSIONS",
        text: str | None = None,
        text_height: float = 0.025,
    ) -> DxfDrawing:
        if radius <= 0:
            raise SceneError("dimension radius must be positive")
        start = promote2(centre)
        end = Vec2(start.x + float(radius) * cos(angle), start.y + float(radius) * sin(angle))
        label = text if text is not None else f"R{_format_measurement(float(radius))}"
        return self._dimension("radius", start, end, 0.0, layer, label, text_height)

    def diameter_dimension(
        self,
        centre: Vec2 | tuple[float, float],
        radius: float,
        *,
        angle: float = 0.0,
        layer: str = "DIMENSIONS",
        text: str | None = None,
        text_height: float = 0.025,
    ) -> DxfDrawing:
        if radius <= 0:
            raise SceneError("dimension radius must be positive")
        start = promote2(centre)
        end = Vec2(start.x + float(radius) * cos(angle), start.y + float(radius) * sin(angle))
        label = text if text is not None else f"DIA {_format_measurement(float(radius) * 2)}"
        return self._dimension("diameter", start, end, 0.0, layer, label, text_height)

    def add_dimension(
        self,
        a: Vec2 | tuple[float, float],
        b: Vec2 | tuple[float, float],
        *,
        offset: float,
        layer: str = "DIMENSIONS",
        text: str | None = None,
        text_height: float = 0.025,
    ) -> DxfDrawing:
        return self.aligned_dimension(
            a, b, offset=offset, layer=layer, text=text, text_height=text_height
        )

    def _require_layer(self, layer: str) -> None:
        if layer not in self.layers:
            raise ValueError(f"layer '{layer}' not registered")

    def angular_dimension(
        self,
        center: tuple[float, float],
        p1: tuple[float, float],
        p2: tuple[float, float],
        distance: float,
        *,
        layer: str,
        dimstyle: str = "PYSEAS",
    ) -> DxfDrawing:
        self._require_layer(layer)
        self.dimensions.append(
            AngularDimensionEntity(
                center=center,
                p1=p1,
                p2=p2,
                distance=distance,
                layer=layer,
                dimstyle=dimstyle,
            )
        )
        return self

    def add_dimension_entity(
        self, dimension: DimensionEntity | AngularDimensionEntity
    ) -> DxfDrawing:
        self.layer(dimension.layer)
        self.dimensions.append(dimension)
        return self

    def _dimension(
        self,
        kind: DimensionKind,
        a: Vec2,
        b: Vec2,
        offset: float,
        layer: str,
        text: str | None,
        text_height: float,
    ) -> DxfDrawing:
        if not layer:
            raise SceneError("dimension layer cannot be empty")
        if text_height <= 0:
            raise SceneError("dimension text height must be positive")
        self.layer(layer)
        label = text if text is not None else _format_measurement((b - a).length())
        self.dimensions.append(
            DimensionEntity(kind, a, b, float(offset), layer, label, text_height)
        )
        return self

    def write(self, path: str | Path) -> DxfDrawing:
        from cad.write.dxf.sections import write_dxf

        write_dxf(self, Path(path))
        return self
