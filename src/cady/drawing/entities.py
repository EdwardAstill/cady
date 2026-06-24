from __future__ import annotations

from dataclasses import dataclass, field

from cady.drawing._geometry import Bounds2, Point2, geometry_bounds, point2


@dataclass(frozen=True, slots=True)
class DrawingEntity:
    geometry: object
    layer: str = "0"

    def __post_init__(self) -> None:
        if not self.layer:
            raise ValueError("entity layer must be non-empty")

    def bounds(self) -> Bounds2:
        return geometry_bounds(self.geometry)

    def to_array(self, *, tolerance: float) -> object:
        converter = getattr(self.geometry, "to_array", None)
        if not callable(converter):
            raise TypeError("drawing geometry must provide to_array(tolerance=...)")
        return converter(tolerance=tolerance)


@dataclass(frozen=True, slots=True)
class Text2D:
    text: str
    at: Point2
    height: float
    layer: str = "0"
    rotation: float = 0.0

    def __post_init__(self) -> None:
        if not self.layer:
            raise ValueError("text layer must be non-empty")
        if self.height <= 0:
            raise ValueError("text height must be positive")
        object.__setattr__(self, "at", point2(self.at, name="text anchor"))
        object.__setattr__(self, "height", float(self.height))
        object.__setattr__(self, "rotation", float(self.rotation))

    def bounds(self) -> Bounds2:
        return self.at, self.at


@dataclass(frozen=True, slots=True)
class Hatch2D:
    boundary: object
    layer: str = "0"
    pattern: str = "ANSI31"
    angle: float = 45.0
    scale: float = 1.0

    def __post_init__(self) -> None:
        if not self.layer:
            raise ValueError("hatch layer must be non-empty")
        if self.pattern.upper() != "ANSI31":
            raise ValueError("only ANSI31 hatch pattern is supported")
        if self.scale <= 0:
            raise ValueError("hatch scale must be positive")
        closed = getattr(self.boundary, "closed", True)
        if closed is False:
            raise ValueError("hatch boundary must be closed")
        object.__setattr__(self, "pattern", self.pattern.upper())
        object.__setattr__(self, "angle", float(self.angle))
        object.__setattr__(self, "scale", float(self.scale))

    def bounds(self) -> Bounds2:
        return geometry_bounds(self.boundary)


@dataclass(frozen=True, slots=True)
class Insert2D:
    name: str
    at: Point2
    layer: str = "0"
    scale: float = 1.0
    rotation: float = 0.0

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("insert block name must be non-empty")
        if not self.layer:
            raise ValueError("insert layer must be non-empty")
        if self.scale <= 0:
            raise ValueError("insert scale must be positive")
        object.__setattr__(self, "at", point2(self.at, name="insert point"))
        object.__setattr__(self, "scale", float(self.scale))
        object.__setattr__(self, "rotation", float(self.rotation))

    def bounds(self) -> Bounds2:
        return self.at, self.at


DrawingPrimitive = DrawingEntity | Text2D | Hatch2D | Insert2D


@dataclass(frozen=True, slots=True)
class BlockDefinition:
    name: str
    base: Point2 = (0.0, 0.0)
    layers: tuple[object, ...] = ()
    entities: tuple[DrawingPrimitive, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("block name must be non-empty")
        object.__setattr__(self, "base", point2(self.base, name="block base"))
        object.__setattr__(self, "layers", tuple(self.layers))
        object.__setattr__(self, "entities", tuple(self.entities))

    def add(self, geometry: object, *, layer: str = "0") -> BlockDefinition:
        return self.add_entity(DrawingEntity(geometry, layer))

    def add_entity(self, entity: DrawingPrimitive) -> BlockDefinition:
        return BlockDefinition(
            self.name,
            self.base,
            self.layers,
            (*self.entities, entity),
        )

    def add_text(
        self,
        text: str,
        *,
        at: object,
        height: float,
        layer: str = "0",
        rotation: float = 0.0,
    ) -> BlockDefinition:
        anchor = point2(at, name="text anchor")
        return self.add_entity(Text2D(text, anchor, height, layer, rotation))

    def hatch(
        self,
        boundary: object,
        *,
        layer: str = "0",
        pattern: str = "ANSI31",
        angle: float = 45.0,
        scale: float = 1.0,
    ) -> BlockDefinition:
        return self.add_entity(Hatch2D(boundary, layer, pattern, angle, scale))

    def bounds(self) -> Bounds2:
        from cady.drawing._geometry import merge_bounds

        return merge_bounds(entity.bounds() for entity in self.entities)
