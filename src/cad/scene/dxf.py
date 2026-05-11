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


@dataclass(frozen=True, slots=True)
class DimStyle:
    """User-configurable dimension style parameters."""

    name: str
    text_height: float = 0.18   # DXF DIMTXT  group 140
    arrow_size: float = 0.18    # DIMASZ       group 41
    decimal_places: int = 4     # DIMDEC       group 271
    extension_offset: float = 0.0625  # DIMEXO group 42
    extension_extend: float = 0.18    # DIMEXE group 44
    text_gap: float = 0.09      # DIMGAP       group 147

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("DimStyle: name must be non-empty")
        if self.decimal_places < 0:
            raise ValueError("DimStyle: decimal_places must be non-negative")
        for field_name in (
            "text_height",
            "arrow_size",
            "extension_offset",
            "extension_extend",
            "text_gap",
        ):
            if getattr(self, field_name) <= 0:
                raise ValueError(f"DimStyle: {field_name} must be positive")


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
    dimstyle: str = "Standard"


@dataclass(frozen=True, slots=True)
class AngularDimensionEntity:
    """3-point angular dimension (vertex + two ray endpoints)."""

    center: tuple[float, float]
    p1: tuple[float, float]
    p2: tuple[float, float]
    distance: float
    layer: str
    dimstyle: str = "Standard"
    measurement_text: str = ""

    def __post_init__(self) -> None:
        if self.distance <= 0:
            raise ValueError("AngularDimensionEntity: distance must be positive")
        v1 = (self.p1[0] - self.center[0], self.p1[1] - self.center[1])
        v2 = (self.p2[0] - self.center[0], self.p2[1] - self.center[1])
        mag1 = math.hypot(*v1)
        mag2 = math.hypot(*v2)
        if mag1 == 0 or mag2 == 0:
            raise ValueError("AngularDimensionEntity: rays must be non-degenerate")
        if self.measurement_text == "":
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


# Group code per header variable. Extend this map as variables are added.
HEADER_VARS: dict[str, int] = {
    "$INSUNITS": 70,
    "$MEASUREMENT": 70,
    "$LUNITS": 70,
    "$AUNITS": 70,
}


def _default_dimstyles() -> dict[str, DimStyle]:
    return {"Standard": DimStyle(name="Standard")}


@dataclass(slots=True)
class DxfDrawing:
    layers: dict[str, Layer] = field(default_factory=dict[str, Layer])
    texts: list[TextEntity] = field(default_factory=list[TextEntity])
    blocks: dict[str, BlockDefinition] = field(default_factory=dict[str, BlockDefinition])
    inserts: list[InsertEntity] = field(default_factory=list[InsertEntity])
    dimensions: list[DimensionEntity | AngularDimensionEntity] = field(
        default_factory=list[DimensionEntity | AngularDimensionEntity]
    )
    _dimstyles: dict[str, DimStyle] = field(default_factory=_default_dimstyles, repr=False)
    _header: dict[str, int | float | str] = field(
        default_factory=dict[str, int | float | str], repr=False
    )

    @property
    def header(self) -> dict[str, int | float | str]:
        return dict(self._header)

    def set_header(self, name: str, value: int | float | str) -> DxfDrawing:
        if name not in HEADER_VARS:
            raise ValueError(f"unknown HEADER variable {name!r}")
        group_code = HEADER_VARS[name]
        # Group codes per AutoCAD DXF reference:
        #   1–9     string
        #   10–59   double
        #   60–79   int16
        #   90–99   int32
        if 1 <= group_code <= 9:
            if not isinstance(value, str):
                raise TypeError(f"HEADER variable {name} requires a str value")
        elif 10 <= group_code <= 59:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise TypeError(f"HEADER variable {name} requires a numeric value")
        elif (60 <= group_code <= 79) or (90 <= group_code <= 99):
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"HEADER variable {name} requires an int value")
        else:
            raise TypeError(f"HEADER variable {name} has unsupported group code {group_code}")
        self._header[name] = value
        return self

    @property
    def hatches(self) -> list[HatchEntity]:
        return [hatch for layer in self.layers.values() for hatch in layer.hatches]

    def dimstyle(self, style: DimStyle) -> DxfDrawing:
        self._dimstyles[style.name] = style
        return self

    @property
    def dimstyles(self) -> tuple[DimStyle, ...]:
        return tuple(self._dimstyles.values())

    def _require_dimstyle(self, name: str) -> None:
        if name not in self._dimstyles:
            raise ValueError(f"dimstyle {name!r} not registered")

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
        a: Vec2 | tuple[float, float] | None = None,
        b: Vec2 | tuple[float, float] | None = None,
        *,
        p1: Vec2 | tuple[float, float] | None = None,
        p2: Vec2 | tuple[float, float] | None = None,
        offset: float,
        layer: str = "DIMENSIONS",
        text: str | None = None,
        text_height: float = 0.025,
        dimstyle: str = "Standard",
    ) -> DxfDrawing:
        # Support both positional (a, b) and keyword (p1, p2) argument styles
        raw_a = a if a is not None else p1
        raw_b = b if b is not None else p2
        if raw_a is None or raw_b is None:
            raise SceneError("linear_dimension requires two points (a, b) or (p1, p2)")
        self._require_dimstyle(dimstyle)
        start = promote2(raw_a)
        end = promote2(raw_b)
        if start == end:
            raise SceneError("dimension points must differ")
        if start.x != end.x and start.y != end.y:
            raise SceneError("linear dimensions require horizontal or vertical points; use aligned")
        return self._dimension("linear", start, end, offset, layer, text, text_height, dimstyle)

    def aligned_dimension(
        self,
        a: Vec2 | tuple[float, float],
        b: Vec2 | tuple[float, float],
        *,
        offset: float,
        layer: str = "DIMENSIONS",
        text: str | None = None,
        text_height: float = 0.025,
        dimstyle: str = "Standard",
    ) -> DxfDrawing:
        self._require_dimstyle(dimstyle)
        start = promote2(a)
        end = promote2(b)
        if start == end:
            raise SceneError("dimension points must differ")
        return self._dimension("aligned", start, end, offset, layer, text, text_height, dimstyle)

    def radius_dimension(
        self,
        centre: Vec2 | tuple[float, float],
        radius: float,
        *,
        angle: float = 0.0,
        layer: str = "DIMENSIONS",
        text: str | None = None,
        text_height: float = 0.025,
        dimstyle: str = "Standard",
    ) -> DxfDrawing:
        self._require_dimstyle(dimstyle)
        if radius <= 0:
            raise SceneError("dimension radius must be positive")
        start = promote2(centre)
        end = Vec2(start.x + float(radius) * cos(angle), start.y + float(radius) * sin(angle))
        label = text if text is not None else f"R{_format_measurement(float(radius))}"
        return self._dimension("radius", start, end, 0.0, layer, label, text_height, dimstyle)

    def diameter_dimension(
        self,
        centre: Vec2 | tuple[float, float],
        radius: float,
        *,
        angle: float = 0.0,
        layer: str = "DIMENSIONS",
        text: str | None = None,
        text_height: float = 0.025,
        dimstyle: str = "Standard",
    ) -> DxfDrawing:
        self._require_dimstyle(dimstyle)
        if radius <= 0:
            raise SceneError("dimension radius must be positive")
        start = promote2(centre)
        end = Vec2(start.x + float(radius) * cos(angle), start.y + float(radius) * sin(angle))
        label = text if text is not None else f"DIA {_format_measurement(float(radius) * 2)}"
        return self._dimension("diameter", start, end, 0.0, layer, label, text_height, dimstyle)

    def add_dimension(
        self,
        a: Vec2 | tuple[float, float],
        b: Vec2 | tuple[float, float],
        *,
        offset: float,
        layer: str = "DIMENSIONS",
        text: str | None = None,
        text_height: float = 0.025,
        dimstyle: str = "Standard",
    ) -> DxfDrawing:
        return self.aligned_dimension(
            a,
            b,
            offset=offset,
            layer=layer,
            text=text,
            text_height=text_height,
            dimstyle=dimstyle,
        )

    def angular_dimension(
        self,
        center: tuple[float, float],
        p1: tuple[float, float],
        p2: tuple[float, float],
        distance: float,
        *,
        layer: str,
        dimstyle: str = "Standard",
    ) -> DxfDrawing:
        self._require_dimstyle(dimstyle)
        self.layer(layer)
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
        self._require_dimstyle(dimension.dimstyle)
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
        dimstyle: str = "Standard",
    ) -> DxfDrawing:
        if not layer:
            raise SceneError("dimension layer cannot be empty")
        if text_height <= 0:
            raise SceneError("dimension text height must be positive")
        self.layer(layer)
        label = text if text is not None else _format_measurement((b - a).length())
        self.dimensions.append(
            DimensionEntity(kind, a, b, float(offset), layer, label, text_height, dimstyle)
        )
        return self

    def write(self, path: str | Path) -> DxfDrawing:
        from cad.write.dxf.sections import write_dxf

        write_dxf(self, Path(path))
        return self
