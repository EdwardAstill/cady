from __future__ import annotations

import pytest

from cady.drawing import (
    AlignedDimension2D,
    AngularDimension2D,
    DiameterDimension2D,
    DimStyle,
    Drawing2D,
    LinearDimension2D,
    RadiusDimension2D,
)


def test_dimension_defaults_format_measurements() -> None:
    assert LinearDimension2D((0, 0), (2, 0), 0.5).text == "2"
    assert AlignedDimension2D((0, 0), (3, 4), 0.5).text == "5"
    assert RadiusDimension2D((0, 0), 2.5).text == "R2.5"
    assert DiameterDimension2D((0, 0), 2.5).text == "DIA 5"
    assert AngularDimension2D((0, 0), (1, 0), (0, 1), 1).text == "90"


def test_linear_dimension_requires_orthogonal_points() -> None:
    with pytest.raises(ValueError, match="horizontal or vertical"):
        LinearDimension2D((0, 0), (1, 1), 0.25)


def test_dimension_entities_auto_create_layer_and_require_registered_style() -> None:
    drawing = Drawing2D().with_dim_style(DimStyle("DETAIL"))

    drawing = drawing.linear_dimension((0, 0), (1, 0), offset=0.2, dim_style="DETAIL")

    assert drawing.layers[0].name == "DIMENSIONS"
    assert drawing.entities[0].dim_style == "DETAIL"
    with pytest.raises(ValueError, match="unknown dimstyle"):
        drawing.aligned_dimension((0, 0), (1, 1), offset=0.1, dim_style="MISSING")


def test_dimstyle_validation() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        DimStyle("")
    with pytest.raises(ValueError, match="non-negative"):
        DimStyle("BAD", decimal_places=-1)
    with pytest.raises(ValueError, match="text_height"):
        DimStyle("BAD", text_height=0)
