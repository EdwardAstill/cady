from __future__ import annotations

import pytest

from cad.geom import midpoint, offset_point, perpendicular
from cad.geom.vec import Vec2


def test_midpoint_returns_average_point() -> None:
    assert midpoint((0, 0), (2, 4)) == Vec2(1, 2)


def test_perpendicular_returns_left_hand_unit_normal() -> None:
    assert perpendicular((2, 0)) == Vec2(0, 1)


def test_perpendicular_rejects_zero_vector() -> None:
    with pytest.raises(ValueError, match="zero"):
        perpendicular((0, 0))


def test_offset_point_moves_along_unit_normal() -> None:
    assert offset_point((1, 2), (0, 3), 0.5) == Vec2(0.5, 2)
