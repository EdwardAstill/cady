from __future__ import annotations

import numpy as np
import pytest

from cady.geometry import (
    Circle2D,
    ClosedPolyline2D,
    Profile2D,
)
from cady.operations import ArrayPolygon2, profile_circle, profile_rectangle
from cady.vec import Vec2


def test_profile_rectangle_returns_polygon_with_expected_bounds() -> None:
    profile = profile_rectangle(4, 2, origin=(1, 2))

    assert profile.bounds() == (Vec2(1, 2), Vec2(5, 4))

    array = profile.to_array(tolerance=0.01)
    assert isinstance(array, ArrayPolygon2)
    np.testing.assert_allclose(array.outer, [[1, 2], [5, 2], [5, 4], [1, 4]])
    assert array.holes == ()


def test_profile_circle_wraps_circle_boundary() -> None:
    profile = profile_circle(2, centre=(3, 4))

    assert isinstance(profile.outer, Circle2D)
    assert profile.bounds() == (Vec2(1, 2), Vec2(5, 6))
    assert len(profile.to_array(tolerance=0.05).outer) >= 12


def test_profile2d_carries_holes_into_polygon_array() -> None:
    profile = Profile2D(
        ClosedPolyline2D(((0, 0), (5, 0), (5, 5), (0, 5))),
        holes=(ClosedPolyline2D(((1, 1), (2, 1), (2, 2), (1, 2))),),
    )

    array = profile.to_array(tolerance=0.01)

    assert isinstance(array, ArrayPolygon2)
    np.testing.assert_allclose(array.outer, [[0, 0], [5, 0], [5, 5], [0, 5]])
    assert len(array.holes) == 1
    np.testing.assert_allclose(array.holes[0], [[1, 1], [2, 1], [2, 2], [1, 2]])


def test_profile_constructors_reject_invalid_dimensions() -> None:
    with pytest.raises(ValueError, match="width must be positive"):
        profile_rectangle(0, 1)
    with pytest.raises(ValueError, match="height must be positive"):
        profile_rectangle(1, -1)
    with pytest.raises(ValueError, match="radius must be positive"):
        profile_circle(0)
