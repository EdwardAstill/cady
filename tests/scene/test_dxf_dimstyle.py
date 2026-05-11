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
