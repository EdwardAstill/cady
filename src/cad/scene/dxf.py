from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

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
            raise SceneError("only ANSI31 hatch pattern is supported in Stage 3")
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

    def add_dimension(self, *args: object, **kwargs: object) -> None:
        raise NotImplementedError("DXF dimensions are reserved for Stage 3")

    def write(self, path: str | Path) -> DxfDrawing:
        from cad.write.dxf.sections import write_dxf

        write_dxf(self, Path(path))
        return self
