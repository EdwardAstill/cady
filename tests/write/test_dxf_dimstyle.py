"""Emitter tests for DIMSTYLE table generation."""

from cad import DimStyle, DxfDrawing
from cad.write.dxf.sections import render_dxf


def test_dimstyle_table_includes_user_dimstyle() -> None:
    drawing = DxfDrawing()
    drawing.dimstyle(DimStyle(name="DETAIL", text_height=3.0, arrow_size=2.0))
    drawing.layer("DIMS")
    drawing.linear_dimension(
        p1=(0.0, 0.0),
        p2=(1.0, 0.0),
        offset=0.5,
        layer="DIMS",
        dimstyle="DETAIL",
    )
    out = render_dxf(drawing)
    assert "\n2\nDETAIL\n" in out


def test_dimstyle_table_writes_text_height_group_140() -> None:
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
    out = render_dxf(drawing)
    # Group 140 = DIMTXT (text height); emitter uses :.8g so 3.0 → "3"
    assert "\n140\n3\n" in out


def test_dimstyle_table_omits_user_styles_when_no_dimensions_use_them() -> None:
    drawing = DxfDrawing()
    drawing.dimstyle(DimStyle(name="UNUSED"))
    drawing.layer("L")
    from cad.geom import line
    drawing.layer("L").add(line((0.0, 0.0), (1.0, 0.0)))
    out = render_dxf(drawing)
    assert "UNUSED" not in out
