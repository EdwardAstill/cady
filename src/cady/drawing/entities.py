"""Drawing entities and reusable block definitions."""

from __future__ import annotations

from dataclasses import dataclass, field

from cady.drawing._geometry import Bounds2, Point2, geometry_bounds


@dataclass(frozen=True, slots=True)
class DrawingEntity:
    """Geometry wrapper that assigns authoring objects to a drawing layer."""

    geometry: object
    layer: str = "0"

    def __post_init__(self) -> None:
        if not self.layer:
            raise ValueError("entity layer must be non-empty")

    def bounds(self) -> Bounds2:
        """Return entity bounds using the wrapped geometry's protocol."""
        return geometry_bounds(self.geometry)

    def to_array(self, *, tolerance: float) -> object:
        """Convert wrapped geometry through its ``to_array`` implementation."""
        converter = getattr(self.geometry, "to_array", None)
        if not callable(converter):
            raise TypeError("drawing geometry must provide to_array(tolerance=...)")
        return converter(tolerance=tolerance)


@dataclass(frozen=True, slots=True)
class Text2:
    """Single-line text annotation anchored at a 2D point."""

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
        object.__setattr__(self, "height", float(self.height))
        object.__setattr__(self, "rotation", float(self.rotation))

    def bounds(self) -> Bounds2:
        return self.at, self.at


@dataclass(frozen=True, slots=True)
class Hatch2:
    """Simple hatch fill for a closed 2D boundary."""

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
class Insert2:
    """Placed instance of a named block definition."""

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
        object.__setattr__(self, "scale", float(self.scale))
        object.__setattr__(self, "rotation", float(self.rotation))

    def bounds(self) -> Bounds2:
        return self.at, self.at


DrawingPrimitive = DrawingEntity | Text2 | Hatch2 | Insert2


@dataclass(frozen=True, slots=True)
class BlockDefinition:
    """Reusable block made from drawing primitives and a base point."""

    name: str
    base: Point2 = (0.0, 0.0)
    layers: tuple[object, ...] = ()
    entities: tuple[DrawingPrimitive, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("block name must be non-empty")
        object.__setattr__(self, "layers", tuple(self.layers))
        object.__setattr__(self, "entities", tuple(self.entities))

    def add_entity(self, entity: DrawingPrimitive) -> BlockDefinition:
        """Return a new block definition with the entity appended."""
        return BlockDefinition(
            self.name,
            self.base,
            self.layers,
            (*self.entities, entity),
        )

    def bounds(self) -> Bounds2:
        from cady.drawing._geometry import merge_bounds

        return merge_bounds(entity.bounds() for entity in self.entities)
