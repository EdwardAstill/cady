from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass
from types import MappingProxyType

import pytest

from cady.drawing import BlockDefinition, Drawing2, DrawingEntity, Hatch2, Layer, Text2


@dataclass(frozen=True)
class Curve:
    min_point: tuple[float, float]
    max_point: tuple[float, float]
    closed: bool = True

    def bounds(self) -> tuple[tuple[float, float], tuple[float, float]]:
        return self.min_point, self.max_point

    def to_array(self, *, tolerance: float) -> tuple[str, float]:
        return "array", tolerance


def test_drawing_adds_geometry_as_entity_and_auto_creates_layer() -> None:
    curve = Curve((0, 0), (2, 1))
    original = Drawing2("front")

    drawing = original.add(curve, layer="GEOM")

    assert original.entities == ()
    assert original.layers == ()
    assert drawing.layers == (Layer("GEOM"),)
    assert drawing.entities == (DrawingEntity(curve, "GEOM"),)


def test_drawing_values_are_frozen_and_mapping_fields_are_read_only() -> None:
    drawing = Drawing2("front").with_metadata("author", "ed")

    with pytest.raises(FrozenInstanceError):
        drawing.name = "other"  # type: ignore[misc]
    assert isinstance(drawing.metadata, MappingProxyType)
    with pytest.raises(TypeError):
        drawing.metadata["author"] = "other"  # type: ignore[index]


def test_add_layer_rejects_conflicting_duplicate() -> None:
    drawing = Drawing2().add_layer(Layer("GEOM", color=3))

    assert drawing.add_layer(Layer("GEOM", color=3)) is drawing
    with pytest.raises(ValueError, match="different settings"):
        drawing.add_layer(Layer("GEOM", color=4))


def test_text_hatch_block_and_insert_entities() -> None:
    profile = Curve((0, 0), (4, 3), closed=True)
    block = BlockDefinition("MARK").add_text("A", at=(1, 2), height=0.5)

    drawing = (
        Drawing2("sheet")
        .add_text("TITLE", at=(10, 20), height=2.5, layer="TEXT")
        .hatch(profile, layer="HATCH")
        .add_block(block)
        .insert("MARK", at=(5, 6), layer="SYMBOLS")
    )

    assert drawing.layers == (Layer("TEXT"), Layer("HATCH"), Layer("SYMBOLS"))
    assert isinstance(drawing.entities[0], Text2)
    assert isinstance(drawing.entities[1], Hatch2)
    assert drawing.block("MARK") == block


def test_insert_requires_known_block() -> None:
    with pytest.raises(ValueError, match="unknown block"):
        Drawing2().insert("MISSING", at=(0, 0))


def test_hatch_requires_closed_boundary() -> None:
    with pytest.raises(ValueError, match="closed"):
        Drawing2().hatch(Curve((0, 0), (1, 0), closed=False))


def test_bounds_include_geometry_text_hatch_inserted_block_and_dimensions() -> None:
    block = BlockDefinition("B").add(Curve((0, 0), (2, 3)))
    drawing = (
        Drawing2("bounded")
        .add(Curve((1, 2), (3, 4)), layer="GEOM")
        .add_text("N", at=(-2, 6), height=0.2)
        .hatch(Curve((5, -1), (6, 1)))
        .add_block(block)
        .insert("B", at=(10, 10), scale=2)
        .linear_dimension((0, 0), (2, 0), offset=-4)
    )

    assert drawing.bounds() == ((-2.0, -4.0), (14.0, 16.0))


def test_to_arrays_returns_geometry_and_hatch_arrays() -> None:
    drawing = Drawing2().add(Curve((0, 0), (1, 1))).hatch(Curve((2, 2), (3, 3)))

    assert drawing.to_arrays(tolerance=0.25) == (("array", 0.25), ("array", 0.25))
