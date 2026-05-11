"""Scene-layer tests for angular dimension entities."""

import math

import pytest

from cad import DxfDrawing
from cad.scene.dxf import AngularDimensionEntity


def test_angular_dimension_records_three_points_and_radius() -> None:
    drawing = DxfDrawing()
    drawing.layer("DIMS", color=2)
    drawing.angular_dimension(
        center=(0.0, 0.0),
        p1=(1.0, 0.0),
        p2=(0.0, 1.0),
        distance=0.5,
        layer="DIMS",
    )
    assert len(drawing.dimensions) == 1
    dim = drawing.dimensions[0]
    assert isinstance(dim, AngularDimensionEntity)
    assert dim.center == (0.0, 0.0)
    assert dim.p1 == (1.0, 0.0)
    assert dim.p2 == (0.0, 1.0)
    assert dim.distance == pytest.approx(0.5)
    assert dim.layer == "DIMS"
    assert dim.measurement_text == "90"


def test_angular_dimension_measurement_uses_degrees() -> None:
    drawing = DxfDrawing()
    drawing.layer("DIMS")
    drawing.angular_dimension(
        center=(0.0, 0.0),
        p1=(1.0, 0.0),
        p2=(math.cos(math.radians(30.0)), math.sin(math.radians(30.0))),
        distance=0.5,
        layer="DIMS",
    )
    assert drawing.dimensions[0].measurement_text == "30"


def test_angular_dimension_rejects_unknown_layer() -> None:
    drawing = DxfDrawing()
    with pytest.raises(ValueError, match="layer 'DIMS' not registered"):
        drawing.angular_dimension(
            center=(0.0, 0.0),
            p1=(1.0, 0.0),
            p2=(0.0, 1.0),
            distance=0.5,
            layer="DIMS",
        )
