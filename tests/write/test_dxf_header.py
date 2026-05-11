"""Emitter tests for HEADER section."""

from cad import DxfDrawing
from cad.geom import line
from cad.write.dxf.sections import render_dxf


def test_header_section_includes_insunits_when_set() -> None:
    drawing = DxfDrawing()
    drawing.set_header("$INSUNITS", 4)
    drawing.layer("L").add(line((0.0, 0.0), (1.0, 0.0)))
    out = render_dxf(drawing)
    # Group code 70 (int16) for INSUNITS, value 4
    assert "$INSUNITS\n70\n4\n" in out


def test_header_section_default_insunits_when_unset() -> None:
    """When the user does not set $INSUNITS, the emitter preserves its existing default (6 = meters)."""
    drawing = DxfDrawing()
    drawing.layer("L").add(line((0.0, 0.0), (1.0, 0.0)))
    out = render_dxf(drawing)
    assert "$INSUNITS\n70\n6\n" in out
