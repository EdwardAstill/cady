from __future__ import annotations

from dataclasses import FrozenInstanceError
from math import pi

import numpy as np
import pytest

from cady.errors import GeometryError
from cady.geometry import (
    Arc2,
    Circle2,
    Ellipse2,
    Line2,
    Mesh2,
    Point2,
    Polyline2,
    Spline2,
)


def test_line2_is_frozen_and_evaluates_to_polyline() -> None:
    line = Line2((0, 0), (2, 3))

    assert line.points() == ((0, 0), (2, 3))
    assert isinstance(line.start, Point2)
    assert line.bounds() == ((0, 0), (2, 3))
    with pytest.raises(FrozenInstanceError):
        line.start = (1, 1)  # type: ignore[misc]

    array = line.to_array(tolerance=0.01)
    assert isinstance(array, np.ndarray)
    np.testing.assert_allclose(array, [[0, 0], [2, 3]])


def test_to_array_requires_explicit_positive_tolerance() -> None:
    line = Line2((0, 0), (1, 0))

    with pytest.raises(TypeError):
        line.to_array()  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="tolerance must be positive"):
        line.to_array(tolerance=0.0)


def test_arc2_samples_with_tolerance() -> None:
    arc = Arc2((0, 0), (2, 0), (2**0.5, 2**0.5))

    start, end = arc.points()
    assert start == (2, 0)
    assert end[0] == pytest.approx(0.0)
    assert end[1] == pytest.approx(2.0)
    assert arc.midpoint == pytest.approx((2**0.5, 2**0.5))
    min_bound, max_bound = arc.bounds()
    assert min_bound[0] == pytest.approx(0.0)
    assert min_bound[1] == pytest.approx(0.0)
    assert max_bound == (2, 2)

    assert not hasattr(arc, "to_array")

    polyline = arc.discretize(tolerance=0.01)
    assert isinstance(polyline, Polyline2)
    assert all(isinstance(curve, Line2) for curve in polyline.curves)
    np.testing.assert_allclose(polyline.vertices[0], [2, 0])
    np.testing.assert_allclose(polyline.vertices[-1], [0, 2], atol=1e-12)
    assert len(polyline.vertices) > 2

    coarse = arc.discretize(tolerance=1.0, min_segments=1)
    limited = arc.discretize(tolerance=1.0, max_segment_length=0.25)
    assert len(limited.vertices) > len(coarse.vertices)


def test_curve2_length_properties_are_exact_for_segments_and_circular_curves() -> None:
    assert Line2((0.0, 0.0), (3.0, 4.0)).length == pytest.approx(5.0)
    assert Arc2(
        (0.0, 0.0),
        (2.0, 0.0),
        (2.0**0.5, 2.0**0.5),
    ).length == pytest.approx(pi)
    assert Circle2((0.0, 0.0), 2.0).length == pytest.approx(4.0 * pi)
    assert Polyline2(((0.0, 0.0), (3.0, 0.0), (3.0, 4.0)), closed=True).length == (
        pytest.approx(12.0)
    )


def test_spline2_length_property_contributes_to_polyline_length() -> None:
    spline = Spline2(((0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)))
    line = Line2((3.0, 0.0), (3.0, 4.0))
    polyline = Polyline2((spline, line))

    assert spline.length == pytest.approx(3.0)
    assert polyline.length == pytest.approx(7.0)


def test_polyline2_open_and_closed_array_flags() -> None:
    open_polyline = Polyline2(((0, 0), (1, 0), (1, 1)))
    closed_polyline = Polyline2(((0, 0), (1, 0), (1, 1), (0, 0)), closed=True)

    open_array = open_polyline.to_array(tolerance=0.01)
    closed_array = closed_polyline.to_array(tolerance=0.01)

    assert isinstance(open_array, np.ndarray)
    assert isinstance(closed_array, np.ndarray)
    np.testing.assert_allclose(open_array, [[0, 0], [1, 0], [1, 1]])
    np.testing.assert_allclose(closed_array, [[0, 0], [1, 0], [1, 1]])


def test_polyline2_start_end_and_reverse() -> None:
    polyline = Polyline2(((0, 0), (1, 0), (1, 1)))

    assert polyline.start == (0, 0)
    assert polyline.end == (1, 1)

    reversed_polyline = polyline.reverse()

    assert reversed_polyline.start == (1, 1)
    assert reversed_polyline.end == (0, 0)
    assert reversed_polyline.points() == ((1, 1), (1, 0), (0, 0))


def test_polyline2_discontinuities_return_sharp_turn_vertices() -> None:
    polyline = Polyline2(((0, 0), (1, 0), (2, 0), (2, 1), (2, 2)))

    assert polyline.discontinuities(min_angle_degrees=45.0) == ((2, 0),)
    assert polyline.discontinuities(min_angle_degrees=100.0) == ()


def test_polyline2_closed_discontinuities_include_wraparound_vertices() -> None:
    polyline = Polyline2(((0, 0), (1, 0), (1, 1), (0, 1)), closed=True)

    assert polyline.discontinuities(min_angle_degrees=80.0) == (
        (0, 0),
        (1, 0),
        (1, 1),
        (0, 1),
    )


def test_polyline2_discontinuities_can_ignore_short_segments() -> None:
    polyline = Polyline2(((0, 0), (0.01, 0), (0.01, 1)))

    assert polyline.discontinuities(
        min_angle_degrees=45.0,
        min_segment_length=0.1,
    ) == ()


def test_polyline2_with_curves_must_be_discretized_before_array_conversion() -> None:
    line = Line2((0.0, 0.0), (1.0, 0.0))
    arc = Arc2(
        (1.0, 1.0),
        (1.0, 0.0),
        (1.0 + 2.0**-0.5, 1.0 - 2.0**-0.5),
    )
    spline = Spline2(((2.0, 1.0), (2.0, 2.0), (3.0, 2.0), (3.0, 1.0)))
    polyline = Polyline2((line, arc, spline))

    with pytest.raises(GeometryError, match="discretize"):
        polyline.to_array(tolerance=0.1)

    coarse = polyline.discretize(tolerance=1.0)
    limited = polyline.discretize(tolerance=1.0, max_segment_length=0.25)
    assert all(isinstance(curve, Line2) for curve in limited.curves)
    assert len(limited.vertices) > len(coarse.vertices)


def test_closed_polyline2_to_mesh_triangulates_boundary() -> None:
    polyline = Polyline2(((0, 0), (1, 0), (1, 1), (0, 1), (0, 0)), closed=True)

    mesh = polyline.to_mesh(tolerance=0.01)

    assert isinstance(mesh, Mesh2)
    assert mesh.vertices == ((0, 0), (1, 0), (1, 1), (0, 1))
    assert len(mesh.faces) == 2
    assert mesh.edges == ((0, 1), (1, 2), (2, 3), (3, 0))
    with pytest.raises(GeometryError, match="closed"):
        Polyline2(((0, 0), (1, 0))).to_mesh(tolerance=0.01)


def test_closed_polyline2_to_mesh_handles_concave_boundary() -> None:
    polyline = Polyline2(((0, 0), (2, 0), (2, 1), (1, 0.5), (0, 1)), closed=True)

    mesh = polyline.to_mesh(tolerance=0.01)

    assert isinstance(mesh, Mesh2)
    assert len(mesh.faces) == 3


def test_circle2_and_ellipse2_are_closed_polyline_arrays() -> None:
    circle = Circle2((1, 2), 3)
    ellipse = Ellipse2((0, 0), 4, 2, rotation_rad=pi / 6)

    assert isinstance(circle.center, Point2)
    assert isinstance(ellipse.center, Point2)
    assert circle.bounds() == ((-2, -1), (4, 5))
    assert ellipse.bounds()[0][0] < -3.5

    circle_array = circle.to_array(tolerance=0.05)
    ellipse_array = ellipse.to_array(tolerance=0.05)

    assert isinstance(circle_array, np.ndarray)
    assert isinstance(ellipse_array, np.ndarray)
    assert len(circle_array) >= 12
    assert len(ellipse_array) >= 12


def test_spline2_samples_cubic_bezier_to_polyline() -> None:
    spline = Spline2(((0, 0), (1, 2), (2, 2), (3, 0)))

    assert not hasattr(spline, "to_array")

    polyline = spline.discretize(tolerance=0.01)
    assert isinstance(polyline, Polyline2)
    assert all(isinstance(curve, Line2) for curve in polyline.curves)
    assert len(polyline.vertices) > 4
    np.testing.assert_allclose(polyline.vertices[0], [0, 0])
    np.testing.assert_allclose(polyline.vertices[-1], [3, 0])

    coarse = spline.discretize(tolerance=0.5)
    limited = spline.discretize(tolerance=0.5, max_segment_length=0.25)
    assert len(limited.vertices) > len(coarse.vertices)


def test_spline2_can_be_defined_by_points_and_vectors() -> None:
    spline = Spline2(
        ((0.0, 0.0), (3.0, 0.0)),
        ((3.0, 0.0), (3.0, 0.0)),
    )

    assert spline.control_points == (
        (0.0, 0.0),
        (1.0, 0.0),
        (2.0, 0.0),
        (3.0, 0.0),
    )
    assert isinstance(spline.control_points[0], Point2)
    assert spline.length == pytest.approx(3.0)


@pytest.mark.parametrize(
    "curve",
    [
        lambda: Line2((0, 0), (0, 0)),
        lambda: Arc2((0, 0), (0, 0), (1, 0)),
        lambda: Polyline2(((0, 0),)),
        lambda: Polyline2(((0, 0), (1, 0)), closed=True),
        lambda: Circle2((0, 0), -1),
        lambda: Ellipse2((0, 0), 1, 0),
        lambda: Spline2(((0, 0), (1, 1), (2, 0))),
    ],
)
def test_curves_reject_invalid_geometry(curve: object) -> None:
    with pytest.raises(ValueError):
        curve()
