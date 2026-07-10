from __future__ import annotations

from dataclasses import FrozenInstanceError
from math import inf, nan

import numpy as np
import pytest

from cady import Line2, Mesh3, Plane3, Point2, Point3, Vector2, Vector3


def test_points_are_immutable_finite_coordinate_values() -> None:
    point2 = Point2(1, 2.5)
    point3 = Point3(1, 2, 3)

    assert (point2.x, point2.y) == (1.0, 2.5)
    assert (point3.x, point3.y, point3.z) == (1.0, 2.0, 3.0)
    assert tuple(point2) == (1.0, 2.5)
    assert np.asarray(point3).tolist() == [1.0, 2.0, 3.0]
    assert point2 == (1.0, 2.5)
    assert hash(point2) == hash((1.0, 2.5))

    with pytest.raises(FrozenInstanceError):
        point2.x = 4.0  # type: ignore[misc]
    with pytest.raises(ValueError, match="finite"):
        Point2(nan, 0.0)
    with pytest.raises(ValueError, match="finite"):
        Point3(0.0, 0.0, inf)
    with pytest.raises(TypeError, match="real numbers"):
        Point2("1", 2.0)


def test_point_arithmetic_follows_affine_rules() -> None:
    start = Point2(1.0, 2.0)
    end = Point2(4.0, 6.0)
    offset = end - start

    assert isinstance(offset, Vector2)
    assert offset == (3.0, 4.0)
    assert start + offset == end
    assert end - offset == start

    with pytest.raises(TypeError):
        _ = start + end  # type: ignore[operator]


def test_vectors_support_direction_operations() -> None:
    vector2 = Vector2(3.0, 4.0)
    x_axis = Vector3(1.0, 0.0, 0.0)
    y_axis = Vector3(0.0, 1.0, 0.0)

    assert vector2.length == pytest.approx(5.0)
    assert vector2.normalized() == pytest.approx((0.6, 0.8))
    assert vector2.dot(Vector2(2.0, 1.0)) == pytest.approx(10.0)
    assert vector2 + Vector2(1.0, -1.0) == (4.0, 3.0)
    assert 2.0 * vector2 == (6.0, 8.0)
    assert x_axis.cross(y_axis) == Vector3(0.0, 0.0, 1.0)
    assert x_axis.dot(y_axis) == 0.0
    assert Point3(0.0, 0.0, 0.0) != Vector3(0.0, 0.0, 0.0)

    with pytest.raises(ValueError, match="zero vector"):
        Vector3(0.0, 0.0, 0.0).normalized()


def test_geometry_accepts_tuples_and_exposes_affine_values() -> None:
    line = Line2((0.0, 0.0), Point2(2.0, 3.0))
    plane = Plane3((0.0, 0.0, 0.0), Vector3(0.0, 0.0, 2.0))
    mesh = Mesh3(
        ((0.0, 0.0, 0.0), Point3(1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
    )

    assert isinstance(line.start, Point2)
    assert isinstance(line.end, Point2)
    assert isinstance(plane.origin, Point3)
    assert isinstance(plane.normal, Vector3)
    assert isinstance(plane.x_axis, Vector3)
    assert isinstance(plane.point(1.0, 2.0), Point3)
    assert all(isinstance(vertex, Point3) for vertex in mesh.vertices)
