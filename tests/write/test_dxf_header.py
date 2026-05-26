"""Emitter tests for HEADER section."""

from cady import DxfDrawing
from cady.geom import line
from cady.write.dxf.sections import render_dxf


def test_header_section_includes_insunits_when_set() -> None:
    drawing = DxfDrawing()
    drawing.set_header("$INSUNITS", 4)
    drawing.layer("L").add(line((0.0, 0.0), (1.0, 0.0)))
    out = render_dxf(drawing)
    # Group code 70 (int16) for INSUNITS, value 4
    assert "$INSUNITS\n70\n4\n" in out


def test_header_section_default_insunits_when_unset() -> None:
    """Preserve the existing default $INSUNITS value when the user does not set it."""
    drawing = DxfDrawing()
    drawing.layer("L").add(line((0.0, 0.0), (1.0, 0.0)))
    out = render_dxf(drawing)
    assert "$INSUNITS\n70\n6\n" in out


def test_header_section_emits_non_insunits_vars() -> None:
    """Variables other than $INSUNITS must also be written to the HEADER section."""
    drawing = DxfDrawing()
    drawing.set_header("$MEASUREMENT", 1)
    drawing.set_header("$LUNITS", 2)
    drawing.layer("L").add(line((0.0, 0.0), (1.0, 0.0)))
    out = render_dxf(drawing)
    assert "$MEASUREMENT\n70\n1\n" in out
    assert "$LUNITS\n70\n2\n" in out
