from __future__ import annotations

import pytest

from cady.geometry import Line2, Line3, Plane3, Surface3
from cady.measurement import (
    InfiniteLine3,
    LineIntersection2,
    LinePlaneIntersection,
    distance,
    intersection,
)


def test_distance_dispatches_points_lines_and_planes() -> None:
    assert distance((0.0, 0.0), (3.0, 4.0)) == 5.0
    assert distance(
        Line3((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        Line3((0.0, 1.0, 0.0), (1.0, 1.0, 0.0)),
    ) == pytest.approx(1.0)

    plane = Plane3.world_xy()
    assert distance(Line3((0.0, 0.0, 1.0), (0.0, 0.0, 2.0)), plane) == pytest.approx(1.0)
    assert distance(Line3((0.0, 0.0, -1.0), (0.0, 0.0, 1.0)), plane) == 0.0


def test_intersection_dispatches_lines_and_planes_with_parameters() -> None:
    line_hit = intersection(
        Line2((0.0, 0.0), (1.0, 1.0)),
        Line2((0.0, 1.0), (1.0, 0.0)),
    )

    assert isinstance(line_hit, LineIntersection2)
    assert line_hit.point == pytest.approx((0.5, 0.5))
    assert line_hit.left_parameter == pytest.approx(0.5)
    assert line_hit.right_parameter == pytest.approx(0.5)

    plane_hit = intersection(
        Line3((0.0, 0.0, -1.0), (0.0, 0.0, 1.0)),
        Plane3.world_xy(),
    )

    assert isinstance(plane_hit, LinePlaneIntersection)
    assert plane_hit.point == pytest.approx((0.0, 0.0, 0.0))
    assert plane_hit.line_parameter == pytest.approx(0.5)


def test_intersection_plane_surfaces_returns_operation_line() -> None:
    first = Surface3.world_xy()
    second = Surface3.plane(origin=(0.0, 2.0, 0.0), normal=(0.0, 1.0, 0.0))

    result = intersection(first, second)

    assert isinstance(result, InfiniteLine3)
    assert result.point == pytest.approx((0.0, 2.0, 0.0))
    assert abs(result.direction[0]) == pytest.approx(1.0)
    assert result.direction[1] == pytest.approx(0.0)
    assert result.direction[2] == pytest.approx(0.0)
