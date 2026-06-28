from __future__ import annotations

import numpy as np
import pytest

from cady.operations.arrays import (
    ArrayBezierSpline2,
    as_points2,
    bounds2,
    evaluate_bezier_spline2,
    polyline2_area,
    polyline2_centroid,
    polyline2_length,
)
from cady.operations.transforms import Transform2


def test_polyline_bounds_length_and_transform() -> None:
    polyline = as_points2([[0.0, 0.0], [3.0, 4.0]], name="vertices")

    min_point, max_point = bounds2(polyline)

    np.testing.assert_allclose(min_point, [0.0, 0.0])
    np.testing.assert_allclose(max_point, [3.0, 4.0])
    assert polyline2_length(polyline) == 5.0
    np.testing.assert_allclose(
        Transform2.translation(1.0, 2.0).apply_points(polyline),
        [[1.0, 2.0], [4.0, 6.0]],
    )


def test_closed_polyline_area_bounds_centroid_and_transform() -> None:
    polyline = as_points2(
        [[0.0, 0.0], [4.0, 0.0], [4.0, 4.0], [0.0, 4.0]],
        name="vertices",
    )

    assert polyline2_area(polyline) == 16.0
    np.testing.assert_allclose(polyline2_centroid(polyline), [2.0, 2.0])
    np.testing.assert_allclose(bounds2(polyline)[1], [4.0, 4.0])
    np.testing.assert_allclose(
        Transform2.translation(1.0, 0.0).apply_points(polyline)[0],
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
    assert sampled.shape == (5, 2)


def test_closed_bezier_sampling_adds_closure_when_needed() -> None:
    spline = ArrayBezierSpline2(
        [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [2.0, 1.0]],
        closed=True,
    )

    sampled = spline.sample(samples=4)

    np.testing.assert_allclose(sampled[0], sampled[-1])
