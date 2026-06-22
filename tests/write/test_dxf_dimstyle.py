"""Emitter tests for DIMSTYLE table generation."""

from cady import DimStyle, DxfDrawing
from cady.files.dxf.sections import render_dxf


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
    from cady.build import line
    drawing.layer("L").add(line((0.0, 0.0), (1.0, 0.0)))
    out = render_dxf(drawing)
    assert "UNUSED" not in out


def test_dimstyle_table_writes_all_field_group_codes() -> None:
    """All six DimStyle fields must map to their correct DXF group codes."""
    drawing = DxfDrawing()
    drawing.dimstyle(
        DimStyle(
            name="DETAIL",
            text_height=3.5,
            arrow_size=2.5,
            decimal_places=2,
            extension_offset=0.7,
            extension_extend=1.3,
            text_gap=0.9,
        )
    )
    drawing.layer("DIMS")
    drawing.linear_dimension(
        p1=(0.0, 0.0), p2=(1.0, 0.0), offset=0.5, layer="DIMS", dimstyle="DETAIL",
    )
    out = render_dxf(drawing)
    assert "\n140\n3.5\n" in out      # text_height
    assert "\n41\n2.5\n" in out       # arrow_size
    assert "\n271\n2\n" in out        # decimal_places
    assert "\n42\n0.7\n" in out       # extension_offset
    assert "\n44\n1.3\n" in out       # extension_extend
    assert "\n147\n0.9\n" in out      # text_gap
