"""Scene-layer tests for custom DIMSTYLE configuration."""

import pytest

from cad import DimStyle, DxfDrawing


def test_dimstyle_defaults_match_existing_builtin() -> None:
    style = DimStyle(name="Standard")
    assert style.text_height == 0.18
    assert style.arrow_size == 0.18
    assert style.decimal_places == 4


def test_dimstyle_can_override_parameters() -> None:
    style = DimStyle(
        name="DETAIL",
        text_height=2.5,
        arrow_size=2.5,
        decimal_places=1,
        extension_offset=1.0,
        extension_extend=1.0,
        text_gap=1.0,
    )
    assert style.text_height == 2.5
    assert style.decimal_places == 1
    assert style.extension_extend == 1.0


def test_drawing_register_dimstyle_makes_it_available() -> None:
    drawing = DxfDrawing()
    drawing.dimstyle(DimStyle(name="DETAIL", text_height=3.0))
    drawing.layer("DIMS")
    drawing.linear_dimension(
        p1=(0.0, 0.0),
        p2=(1.0, 0.0),
        offset=0.5,
        layer="DIMS",
        dimstyle="DETAIL",
    )
    assert drawing.dimensions[0].dimstyle == "DETAIL"


def test_drawing_rejects_dimension_for_unknown_dimstyle() -> None:
    drawing = DxfDrawing()
    drawing.layer("DIMS")
    with pytest.raises(ValueError, match="dimstyle 'DETAIL' not registered"):
        drawing.linear_dimension(
            p1=(0.0, 0.0),
            p2=(1.0, 0.0),
            offset=0.5,
            layer="DIMS",
            dimstyle="DETAIL",
        )


def test_dimstyle_rejects_non_positive_text_height() -> None:
    with pytest.raises(ValueError, match="text_height must be positive"):
        DimStyle(name="X", text_height=0.0)


def test_dimstyle_rejects_negative_arrow_size() -> None:
    with pytest.raises(ValueError, match="arrow_size must be positive"):
        DimStyle(name="X", arrow_size=-0.1)


def test_dimstyle_rejects_zero_text_gap() -> None:
    with pytest.raises(ValueError, match="text_gap must be positive"):
        DimStyle(name="X", text_gap=0.0)


def test_add_dimension_entity_rejects_unknown_dimstyle() -> None:
    from cad.scene.dxf import AngularDimensionEntity

    drawing = DxfDrawing()
    entity = AngularDimensionEntity(
        center=(0.0, 0.0),
        p1=(1.0, 0.0),
        p2=(0.0, 1.0),
        distance=0.5,
        layer="DIMS",
        dimstyle="DETAIL",
    )
    with pytest.raises(ValueError, match="dimstyle 'DETAIL' not registered"):
        drawing.add_dimension_entity(entity)
