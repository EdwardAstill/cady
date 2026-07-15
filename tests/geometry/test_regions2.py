from __future__ import annotations

import numpy as np
import pytest

from cady.geometry import (
    Circle2,
    Polyline2,
    Region2,
)


def test_region_rectangle_returns_closed_polyline_with_expected_bounds() -> None:
    region = Region2.rectangle(4, 2, origin=(1, 2))

    assert region.bounds() == ((1, 2), (5, 4))
    assert region.boundary == ((1, 2), (5, 4))

    array = region.to_array(tolerance=0.01)
    assert isinstance(array, np.ndarray)
    np.testing.assert_allclose(array, [[1, 2], [5, 2], [5, 4], [1, 4]])


def test_region_circle_wraps_circle_boundary() -> None:
    region = Region2.circle(2, center=(3, 4))

    assert isinstance(region.outer, Circle2)
    assert region.bounds() == ((1, 2), (5, 6))
    array = region.to_array(tolerance=0.05)
    assert isinstance(array, np.ndarray)
    assert len(array) >= 12


def test_region2_carries_holes_as_closed_polyline_loops() -> None:
    region = Region2(
        Polyline2(((0, 0), (5, 0), (5, 5), (0, 5)), closed=True),
        holes=(Polyline2(((1, 1), (2, 1), (2, 2), (1, 2)), closed=True),),
    )

    outer, hole = region.loops(tolerance=0.01)

    assert isinstance(outer, np.ndarray)
    assert isinstance(hole, np.ndarray)
    np.testing.assert_allclose(outer, [[0, 0], [5, 0], [5, 5], [0, 5]])
    np.testing.assert_allclose(hole, [[1, 1], [2, 1], [2, 2], [1, 2]])


def test_region2_rejects_open_outer_at_construction() -> None:
    with pytest.raises(ValueError, match="region outer boundary must be closed"):
        Region2(Polyline2(((0, 0), (1, 0), (1, 1))))


def test_region2_rejects_open_hole_at_construction() -> None:
    outer = Polyline2(((0, 0), (2, 0), (2, 2), (0, 2)), closed=True)
    hole = Polyline2(((0.5, 0.5), (1.5, 0.5), (1.5, 1.5)))

    with pytest.raises(ValueError, match=r"region holes\[0\] boundary must be closed"):
        Region2(outer, holes=(hole,))


def test_region_constructors_reject_invalid_dimensions() -> None:
    with pytest.raises(ValueError, match="width must be positive"):
        Region2.rectangle(0, 1)
    with pytest.raises(ValueError, match="height must be positive"):
        Region2.rectangle(1, -1)
    with pytest.raises(ValueError, match="radius must be positive"):
        Region2.circle(0)
