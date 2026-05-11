"""Emitter tests for angular dimensions."""

from cad import DxfDrawing
from cad.write.dxf.sections import render_dxf


def test_angular_dimension_emits_dimension_entity() -> None:
    drawing = DxfDrawing()
    drawing.layer("DIMS")
    drawing.angular_dimension(
        center=(0.0, 0.0), p1=(1.0, 0.0), p2=(0.0, 1.0), distance=0.5, layer="DIMS",
    )
    out = render_dxf(drawing)
    assert "DIMENSION" in out
    assert "AcDb3PointAngularDimension" in out
    assert "\n70\n5\n" in out


def test_angular_dimension_block_definition_present() -> None:
    drawing = DxfDrawing()
    drawing.layer("DIMS")
    drawing.angular_dimension(
        center=(0.0, 0.0), p1=(1.0, 0.0), p2=(0.0, 1.0), distance=0.5, layer="DIMS",
    )
    out = render_dxf(drawing)
    assert out.count("\nAcDbBlockBegin\n2\n*D") == 1
