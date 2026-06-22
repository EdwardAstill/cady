"""Scene-layer tests for angular dimension entities."""

import math

import pytest

from cady import DxfDrawing
from cady.domain.drawing import AngularDimensionEntity


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


def test_angular_dimension_auto_creates_unknown_layer() -> None:
    drawing = DxfDrawing()
    drawing.angular_dimension(
        center=(0.0, 0.0),
        p1=(1.0, 0.0),
        p2=(0.0, 1.0),
        distance=0.5,
        layer="DIMS",
    )
    assert "DIMS" in drawing.layers


def test_angular_dimension_rejects_zero_length_ray() -> None:
    with pytest.raises(ValueError, match="rays must be non-degenerate"):
        AngularDimensionEntity(
            center=(0.0, 0.0),
            p1=(0.0, 0.0),
            p2=(1.0, 0.0),
            distance=0.5,
            layer="DIMS",
            measurement_text="45",
        )


def test_add_dimension_entity_accepts_angular() -> None:
    drawing = DxfDrawing()
    entity = AngularDimensionEntity(
        center=(0.0, 0.0),
        p1=(1.0, 0.0),
        p2=(0.0, 1.0),
        distance=0.5,
        layer="DIMS",
    )
    drawing.add_dimension_entity(entity)
    assert len(drawing.dimensions) == 1
    assert drawing.dimensions[0] is entity
    assert "DIMS" in drawing.layers
