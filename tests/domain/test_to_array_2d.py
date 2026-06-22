from __future__ import annotations

from math import isclose

from cady import circle, line, polyline, rectangle, spline
from cady.numeric import ArrayBezierSpline2, ArrayPolygon2, ArrayPolyline2


def test_open_line_converts_to_array_polyline() -> None:
    array = line((0, 0), (1, 0)).to_array()
    assert isinstance(array, ArrayPolyline2)
    assert array.vertices.shape == (2, 2)
    assert not array.closed


def test_closed_profile_with_hole_converts_to_array_polygon() -> None:
    profile = rectangle((0, 0), (2, 1)).with_hole(circle((1, 0.5), 0.2))
    array = profile.to_array(tolerance=1e-2)
    assert isinstance(array, ArrayPolygon2)
    assert len(array.holes) == 1
    assert isclose(array.area(), 2.0 - 3.14159 * 0.2**2, rel_tol=0.04)


def test_open_polyline_and_spline_keep_numeric_shape() -> None:
    path = polyline([(0, 0), (1, 0), (1, 1)])
    path_array = path.to_array()
    assert isinstance(path_array, ArrayPolyline2)

    curve = spline([(0, 0), (0.25, 0.5), (0.75, 0.5), (1, 0)])
    curve_array = curve.to_array()
    assert isinstance(curve_array, ArrayBezierSpline2)
    assert curve_array.control_points.shape == (4, 2)
