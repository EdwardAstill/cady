"""Public bounds property on DxfDrawing."""

import pytest

from cad import DxfDrawing
from cad.geom import circle, line


def test_bounds_for_empty_drawing_is_zero_zero() -> None:
    drawing = DxfDrawing()
    lo, hi = drawing.bounds
    assert lo == (0.0, 0.0)
    assert hi == (0.0, 0.0)


def test_bounds_covers_lines_and_circles() -> None:
    drawing = DxfDrawing()
    drawing.layer("GEOM").add(line((0.0, 0.0), (10.0, 5.0)))
    drawing.layer("GEOM").add(circle((3.0, -2.0), 1.5))
    lo, hi = drawing.bounds
    assert (lo.x, lo.y) == pytest.approx((0.0, -3.5))
    assert (hi.x, hi.y) == pytest.approx((10.0, 5.0))
