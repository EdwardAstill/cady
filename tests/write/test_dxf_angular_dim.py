"""Emitter tests for angular dimensions."""

import math

from cady import DxfDrawing
from cady.files.dxf.sections import render_dxf


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


def test_angular_dimension_def_point_is_arc_location() -> None:
    """Group 10 (AcDbDimension definition point) must equal group 16 (arc point)."""
    drawing = DxfDrawing()
    drawing.layer("DIMS")
    drawing.angular_dimension(
        center=(0.0, 0.0),
        p1=(1.0, 0.0),
        p2=(0.0, 1.0),
        distance=2.0,
        layer="DIMS",
    )
    out = render_dxf(drawing)
    # Bisector of (1,0) and (0,1) at distance 2 is approximately (1.414..., 1.414...).
    # The emitter's group 10/20 (AcDbDimension def point) must match group 16/26 (arc point).
    # If the def point were center (0, 0), this assertion would fail.
    lines = out.splitlines()
    # Find first DIMENSION entity occurrence
    i = lines.index("DIMENSION")
    # Within the next 80 lines collect (group, value) pairs
    g10_value: str | None = None
    g16_value: str | None = None
    j = i + 1
    while j < min(i + 80, len(lines) - 1):
        if lines[j] == "10" and g10_value is None:
            g10_value = lines[j + 1]
        if lines[j] == "16":
            g16_value = lines[j + 1]
        j += 1
    assert g10_value is not None
    assert g16_value is not None
    assert g10_value == g16_value
    # Sanity-check that the def point is not the center (0).
    assert g10_value not in ("0", "0.0")


def test_angular_dimension_uses_standard_dimstyle_by_default() -> None:
    drawing = DxfDrawing()
    drawing.layer("DIMS")
    drawing.angular_dimension(
        center=(0.0, 0.0), p1=(1.0, 0.0), p2=(0.0, 1.0), distance=0.5, layer="DIMS",
    )
    out = render_dxf(drawing)
    # Group code 3 in DIMENSION entity = dimstyle name reference
    assert "\n3\nStandard\n" in out
    assert "\n3\nPYSEAS\n" not in out


def test_angular_dimension_bounds_include_arc_point() -> None:
    """When distance > ray length, arc point must extend the bbox."""
    drawing = DxfDrawing()
    drawing.layer("DIMS")
    # Rays at length 1; distance 5 places arc point far outside p1/p2 hull.
    drawing.angular_dimension(
        center=(0.0, 0.0),
        p1=(1.0, 0.0),
        p2=(0.0, 1.0),
        distance=5.0,
        layer="DIMS",
    )
    out = render_dxf(drawing)
    arc_coord = 5.0 / math.sqrt(2.0)
    # Parse $EXTMAX block: $EXTMAX\n 10\n<x>\n 20\n<y>\n
    lines = out.splitlines()
    i = lines.index("$EXTMAX")
    # Next "10" is x, next "20" is y
    x_idx = lines.index("10", i)
    extmax_x = float(lines[x_idx + 1])
    # If bounds omitted arc_pt, extmax_x would be 1.0 (max of center/p1/p2).
    assert extmax_x >= arc_coord - 0.01
