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
    Polyline2,
    Spline2,
)


def test_line2_is_frozen_and_evaluates_to_polyline() -> None:
    line = Line2((0, 0), (2, 3))

    assert line.points() == ((0, 0), (2, 3))
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
    arc = Arc2((0, 0), 2, 0, pi / 2)

    start, end = arc.points()
    assert start == (2, 0)
    assert end[0] == pytest.approx(0.0)
    assert end[1] == pytest.approx(2.0)
    min_bound, max_bound = arc.bounds()
    assert min_bound[0] == pytest.approx(0.0)
    assert min_bound[1] == pytest.approx(0.0)
    assert max_bound == (2, 2)

    array = arc.to_array(tolerance=0.01)
    assert isinstance(array, np.ndarray)
    assert len(array) > 2
    np.testing.assert_allclose(array[0], [2, 0])
    np.testing.assert_allclose(array[-1], [0, 2], atol=1e-12)


def test_polyline2_open_and_closed_array_flags() -> None:
    open_polyline = Polyline2(((0, 0), (1, 0), (1, 1)))
    closed_polyline = Polyline2(((0, 0), (1, 0), (1, 1), (0, 0)), closed=True)

    open_array = open_polyline.to_array(tolerance=0.01)
    closed_array = closed_polyline.to_array(tolerance=0.01)

    assert isinstance(open_array, np.ndarray)
    assert isinstance(closed_array, np.ndarray)
    np.testing.assert_allclose(open_array, [[0, 0], [1, 0], [1, 1]])
    np.testing.assert_allclose(closed_array, [[0, 0], [1, 0], [1, 1]])


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

    array = spline.to_array(tolerance=0.01)

    assert isinstance(array, np.ndarray)
    assert len(array) > 4
    np.testing.assert_allclose(array[0], [0, 0])
    np.testing.assert_allclose(array[-1], [3, 0])


@pytest.mark.parametrize(
    "curve",
    [
        lambda: Line2((0, 0), (0, 0)),
        lambda: Arc2((0, 0), 0, 0, 1),
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
