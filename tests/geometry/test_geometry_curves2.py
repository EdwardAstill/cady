from __future__ import annotations

from dataclasses import FrozenInstanceError
from math import pi

import numpy as np
import pytest

from cady.geometry import (
    Arc2,
    Circle2,
    ClosedPolyline2,
    Ellipse2,
    Line2,
    Mesh2,
    Polyline2,
    Spline2,
)
from cady.operations import ArrayPolygon2, ArrayPolyline2
from cady.vec import Vec2


def test_line2_is_frozen_and_evaluates_to_polyline() -> None:
    line = Line2((0, 0), (2, 3))

    assert line.points() == (Vec2(0, 0), Vec2(2, 3))
    assert line.bounds() == (Vec2(0, 0), Vec2(2, 3))
    with pytest.raises(FrozenInstanceError):
        line.start = Vec2(1, 1)  # type: ignore[misc]

    array = line.to_array(tolerance=0.01)
    assert isinstance(array, ArrayPolyline2)
    assert not array.closed
    np.testing.assert_allclose(array.vertices, [[0, 0], [2, 3]])


def test_to_array_requires_explicit_positive_tolerance() -> None:
    line = Line2((0, 0), (1, 0))

    with pytest.raises(TypeError):
        line.to_array()  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="tolerance must be positive"):
        line.to_array(tolerance=0.0)


def test_arc2_samples_with_tolerance() -> None:
    arc = Arc2((0, 0), 2, 0, pi / 2)

    start, end = arc.points()
    assert start == Vec2(2, 0)
    assert end.x == pytest.approx(0.0)
    assert end.y == pytest.approx(2.0)
    min_bound, max_bound = arc.bounds()
    assert min_bound.x == pytest.approx(0.0)
    assert min_bound.y == pytest.approx(0.0)
    assert max_bound == Vec2(2, 2)

    array = arc.to_array(tolerance=0.01)
    assert isinstance(array, ArrayPolyline2)
    assert len(array.vertices) > 2
    np.testing.assert_allclose(array.vertices[0], [2, 0])
    np.testing.assert_allclose(array.vertices[-1], [0, 2], atol=1e-12)


def test_polyline2_and_closed_polyline2_array_types() -> None:
    open_polyline = Polyline2(((0, 0), (1, 0), (1, 1)))
    closed_polyline = ClosedPolyline2(((0, 0), (1, 0), (1, 1), (0, 0)))

    open_array = open_polyline.to_array(tolerance=0.01)
    closed_array = closed_polyline.to_array(tolerance=0.01)

    assert isinstance(open_array, ArrayPolyline2)
    assert isinstance(closed_array, ArrayPolygon2)
    np.testing.assert_allclose(open_array.vertices, [[0, 0], [1, 0], [1, 1]])
    np.testing.assert_allclose(closed_array.outer, [[0, 0], [1, 0], [1, 1]])


def test_closed_polyline2_to_mesh_triangulates_boundary() -> None:
    polyline = ClosedPolyline2(((0, 0), (1, 0), (1, 1), (0, 1), (0, 0)))

    mesh = polyline.to_mesh(tolerance=0.01)

    assert isinstance(mesh, Mesh2)
    assert mesh.vertices == (Vec2(0, 0), Vec2(1, 0), Vec2(1, 1), Vec2(0, 1))
    assert len(mesh.faces) == 2
    assert mesh.edges == ((0, 1), (1, 2), (2, 3), (3, 0))
    assert not hasattr(Polyline2(((0, 0), (1, 0))), "to_mesh")


def test_closed_polyline2_to_mesh_handles_concave_boundary() -> None:
    polyline = ClosedPolyline2(((0, 0), (2, 0), (2, 1), (1, 0.5), (0, 1)))

    mesh = polyline.to_mesh(tolerance=0.01)

    assert isinstance(mesh, Mesh2)
    assert len(mesh.faces) == 3


def test_circle2_and_ellipse2_are_closed_polygon_arrays() -> None:
    circle = Circle2((1, 2), 3)
    ellipse = Ellipse2((0, 0), 4, 2, rotation_rad=pi / 6)

    assert circle.bounds() == (Vec2(-2, -1), Vec2(4, 5))
    assert ellipse.bounds()[0].x < -3.5

    circle_array = circle.to_array(tolerance=0.05)
    ellipse_array = ellipse.to_array(tolerance=0.05)

    assert isinstance(circle_array, ArrayPolygon2)
    assert isinstance(ellipse_array, ArrayPolygon2)
    assert len(circle_array.outer) >= 12
    assert len(ellipse_array.outer) >= 12


def test_spline2_samples_cubic_bezier_to_polyline() -> None:
    spline = Spline2(((0, 0), (1, 2), (2, 2), (3, 0)))

    array = spline.to_array(tolerance=0.01)

    assert isinstance(array, ArrayPolyline2)
    assert len(array.vertices) > 4
    np.testing.assert_allclose(array.vertices[0], [0, 0])
    np.testing.assert_allclose(array.vertices[-1], [3, 0])


@pytest.mark.parametrize(
    "curve",
    [
        lambda: Line2((0, 0), (0, 0)),
        lambda: Arc2((0, 0), 0, 0, 1),
        lambda: Polyline2(((0, 0),)),
        lambda: ClosedPolyline2(((0, 0), (1, 0))),
        lambda: Circle2((0, 0), -1),
        lambda: Ellipse2((0, 0), 1, 0),
        lambda: Spline2(((0, 0), (1, 1), (2, 0))),
    ],
)
def test_curves_reject_invalid_geometry(curve: object) -> None:
    with pytest.raises(ValueError):
        curve()
