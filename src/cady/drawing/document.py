from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType

from cady.drawing._geometry import Bounds2, merge_bounds, point2, transformed_bounds
from cady.drawing.dimensions import (
    AlignedDimension2D,
    AngularDimension2D,
    DiameterDimension2D,
    Dimension2D,
    DimStyle,
    LinearDimension2D,
    RadiusDimension2D,
)
from cady.drawing.entities import BlockDefinition, DrawingEntity, Hatch2D, Insert2D, Text2D
from cady.drawing.layers import Layer

DrawingItem = DrawingEntity | Text2D | Hatch2D | Insert2D | Dimension2D


def _default_dim_styles() -> tuple[DimStyle, ...]:
    return (DimStyle(),)


def _empty_header() -> dict[str, int | float | str]:
    return {}


def _empty_metadata() -> dict[str, object]:
    return {}


@dataclass(frozen=True, slots=True)
class Drawing2D:
    name: str = "drawing"
    units: str = "m"
    layers: tuple[Layer, ...] = ()
    entities: tuple[DrawingItem, ...] = ()
    blocks: tuple[BlockDefinition, ...] = ()
    dim_styles: tuple[DimStyle, ...] = field(default_factory=_default_dim_styles)
    header: Mapping[str, int | float | str] = field(default_factory=_empty_header)
    metadata: Mapping[str, object] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("drawing name must be non-empty")
        if not self.units:
            raise ValueError("drawing units must be non-empty")

        layers = tuple(self.layers)
        entities = tuple(self.entities)
        blocks = tuple(self.blocks)
        dim_styles = tuple(self.dim_styles) or _default_dim_styles()

        _check_unique((layer.name for layer in layers), "layer")
        _check_unique((block.name for block in blocks), "block")
        _check_unique((style.name for style in dim_styles), "dimstyle")

        object.__setattr__(self, "layers", layers)
        object.__setattr__(self, "entities", entities)
        object.__setattr__(self, "blocks", blocks)
        object.__setattr__(self, "dim_styles", dim_styles)
        object.__setattr__(self, "header", MappingProxyType(dict(self.header)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def add_layer(
        self,
        layer: Layer | str,
        *,
        color: int = 7,
        linetype: str = "CONTINUOUS",
    ) -> Drawing2D:
        value = layer if isinstance(layer, Layer) else Layer(layer, color=color, linetype=linetype)
        existing = self.layer(value.name)
        if existing == value:
            return self
        if existing is not None:
            raise ValueError(f"layer already exists with different settings: {value.name}")
        return replace(self, layers=(*self.layers, value))

    def with_layer(
        self,
        layer: Layer | str,
        *,
        color: int = 7,
        linetype: str = "CONTINUOUS",
    ) -> Drawing2D:
        return self.add_layer(layer, color=color, linetype=linetype)

    def layer(self, name: str) -> Layer | None:
        return next((layer for layer in self.layers if layer.name == name), None)

    def add(self, geometry: object, *, layer: str = "0") -> Drawing2D:
        return self.add_entity(DrawingEntity(geometry, layer))

    def add_entity(self, entity: DrawingItem) -> Drawing2D:
        drawing = self._with_entity_layers(entity)
        drawing._validate_entity(entity)
        return replace(drawing, entities=(*drawing.entities, entity))

    def add_text(
        self,
        text: str,
        *,
        at: object,
        height: float,
        layer: str = "0",
        rotation: float = 0.0,
    ) -> Drawing2D:
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
    ) -> Drawing2D:
        return self.add_entity(Hatch2D(boundary, layer, pattern, angle, scale))

    def add_block(self, block: BlockDefinition) -> Drawing2D:
        if self.block(block.name) is not None:
            raise ValueError(f"block already exists: {block.name}")
        return replace(self, blocks=(*self.blocks, block))

    def block(self, name: str) -> BlockDefinition | None:
        return next((block for block in self.blocks if block.name == name), None)

    def insert(
        self,
        name: str,
        *,
        at: object,
        layer: str = "0",
        scale: float = 1.0,
        rotation: float = 0.0,
    ) -> Drawing2D:
        if self.block(name) is None:
            raise ValueError(f"unknown block: {name}")
        insert_at = point2(at, name="insert point")
        return self.add_entity(Insert2D(name, insert_at, layer, scale, rotation))

    def with_dim_style(self, style: DimStyle) -> Drawing2D:
        existing = self.dim_style(style.name)
        if existing == style:
            return self
        if existing is not None:
            raise ValueError(f"dimstyle already exists with different settings: {style.name}")
        return replace(self, dim_styles=(*self.dim_styles, style))

    def dim_style(self, name: str) -> DimStyle | None:
        return next((style for style in self.dim_styles if style.name == name), None)

    def add_dimension(self, dimension: Dimension2D) -> Drawing2D:
        return self.add_entity(dimension)

    def linear_dimension(
        self,
        p1: object,
        p2: object,
        *,
        offset: float,
        layer: str = "DIMENSIONS",
        text: str | None = None,
        text_height: float = 0.025,
        dim_style: str = "Standard",
    ) -> Drawing2D:
        return self.add_dimension(
            LinearDimension2D(
                point2(p1, name="dimension p1"),
                point2(p2, name="dimension p2"),
                offset,
                layer,
                text,
                text_height,
                dim_style,
            )
        )

    def aligned_dimension(
        self,
        p1: object,
        p2: object,
        *,
        offset: float,
        layer: str = "DIMENSIONS",
        text: str | None = None,
        text_height: float = 0.025,
        dim_style: str = "Standard",
    ) -> Drawing2D:
        return self.add_dimension(
            AlignedDimension2D(
                point2(p1, name="dimension p1"),
                point2(p2, name="dimension p2"),
                offset,
                layer,
                text,
                text_height,
                dim_style,
            )
        )

    def radius_dimension(
        self,
        center: object,
        radius: float,
        *,
        angle: float = 0.0,
        layer: str = "DIMENSIONS",
        text: str | None = None,
        text_height: float = 0.025,
        dim_style: str = "Standard",
    ) -> Drawing2D:
        return self.add_dimension(
            RadiusDimension2D(
                point2(center, name="dimension center"),
                radius,
                angle,
                layer,
                text,
                text_height,
                dim_style,
            )
        )

    def diameter_dimension(
        self,
        center: object,
        radius: float,
        *,
        angle: float = 0.0,
        layer: str = "DIMENSIONS",
        text: str | None = None,
        text_height: float = 0.025,
        dim_style: str = "Standard",
    ) -> Drawing2D:
        return self.add_dimension(
            DiameterDimension2D(
                point2(center, name="dimension center"),
                radius,
                angle,
                layer,
                text,
                text_height,
                dim_style,
            )
        )

    def angular_dimension(
        self,
        center: object,
        p1: object,
        p2: object,
        distance: float,
        *,
        layer: str = "DIMENSIONS",
        text: str | None = None,
        text_height: float = 0.025,
        dim_style: str = "Standard",
    ) -> Drawing2D:
        return self.add_dimension(
            AngularDimension2D(
                point2(center, name="angular dimension center"),
                point2(p1, name="angular dimension p1"),
                point2(p2, name="angular dimension p2"),
                distance,
                layer,
                text,
                text_height,
                dim_style,
            )
        )

    def with_header(self, name: str, value: int | float | str) -> Drawing2D:
        header = dict(self.header)
        header[name] = value
        return replace(self, header=header)

    def with_metadata(self, name: str, value: object) -> Drawing2D:
        metadata = dict(self.metadata)
        metadata[name] = value
        return replace(self, metadata=metadata)

    def bounds(self) -> Bounds2:
        return merge_bounds(self._entity_bounds(entity) for entity in self.entities)

    def to_arrays(self, *, tolerance: float) -> tuple[object, ...]:
        arrays: list[object] = []
        for entity in self.entities:
            if isinstance(entity, DrawingEntity):
                arrays.append(entity.to_array(tolerance=tolerance))
            elif isinstance(entity, Hatch2D):
                converter = getattr(entity.boundary, "to_array", None)
                if callable(converter):
                    arrays.append(converter(tolerance=tolerance))
        return tuple(arrays)

    def _with_entity_layers(self, entity: DrawingItem) -> Drawing2D:
        layer = getattr(entity, "layer", None)
        if isinstance(layer, str) and self.layer(layer) is None:
            return self.add_layer(layer)
        return self

    def _validate_entity(self, entity: DrawingItem) -> None:
        dim_style = getattr(entity, "dim_style", None)
        if isinstance(dim_style, str) and self.dim_style(dim_style) is None:
            raise ValueError(f"unknown dimstyle: {dim_style}")
        if isinstance(entity, Insert2D) and self.block(entity.name) is None:
            raise ValueError(f"unknown block: {entity.name}")

    def _entity_bounds(self, entity: DrawingItem) -> Bounds2:
        if isinstance(entity, Insert2D):
            block = self.block(entity.name)
            if block is None:
                return entity.bounds()
            return transformed_bounds(
                block.bounds(),
                at=entity.at,
                scale=entity.scale,
                rotation=entity.rotation,
            )
        return entity.bounds()


def _check_unique(values: Iterable[str], label: str) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"duplicate {label} name: {value}")
        seen.add(value)
