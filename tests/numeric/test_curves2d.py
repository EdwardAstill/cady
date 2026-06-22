from __future__ import annotations

import numpy as np
import pytest

from cady.numeric.curves2d import ArrayBezierSpline2, evaluate_bezier_spline2
from cady.numeric.paths2d import ArrayPolygon2, ArrayPolyline2
from cady.numeric.transform import Transform2


def test_polyline_bounds_length_and_transform() -> None:
    polyline = ArrayPolyline2([[0.0, 0.0], [3.0, 4.0]], closed=False)

    min_point, max_point = polyline.bounds()

    np.testing.assert_allclose(min_point, [0.0, 0.0])
    np.testing.assert_allclose(max_point, [3.0, 4.0])
    assert polyline.length() == 5.0
    np.testing.assert_allclose(
        polyline.transformed(Transform2.translation(1.0, 2.0)).vertices,
        [[1.0, 2.0], [4.0, 6.0]],
    )


def test_polygon_area_bounds_centroid_and_holes() -> None:
    polygon = ArrayPolygon2(
        [[0.0, 0.0], [4.0, 0.0], [4.0, 4.0], [0.0, 4.0]],
        holes=(np.array([[1.0, 1.0], [3.0, 1.0], [3.0, 3.0], [1.0, 3.0]]),),
    )

    assert polygon.area() == 12.0
    np.testing.assert_allclose(polygon.centroid(), [2.0, 2.0])
    np.testing.assert_allclose(polygon.bounds()[1], [4.0, 4.0])
    np.testing.assert_allclose(
        polygon.transformed(Transform2.translation(1.0, 0.0)).outer[0],
        [1.0, 0.0],
    )


def test_bezier_spline_validates_3n_plus_1_control_points() -> None:
    with pytest.raises(ValueError, match="3n \\+ 1"):
        ArrayBezierSpline2([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])


def test_bezier_evaluation_endpoints_and_sampling() -> None:
    spline = ArrayBezierSpline2(
        [[0.0, 0.0], [1.0, 0.0], [2.0, 1.0], [3.0, 1.0]],
        closed=False,
    )

    points = evaluate_bezier_spline2(spline, [0.0, 1.0])
    sampled = spline.sample(samples=5)

    np.testing.assert_allclose(points, [[0.0, 0.0], [3.0, 1.0]])
    assert sampled.vertices.shape == (5, 2)
    assert sampled.closed is False


def test_closed_bezier_sampling_adds_closure_when_needed() -> None:
    spline = ArrayBezierSpline2(
        [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [2.0, 1.0]],
        closed=True,
    )

    sampled = spline.sample(samples=4)

    assert sampled.closed is True
    np.testing.assert_allclose(sampled.vertices[0], sampled.vertices[-1])

