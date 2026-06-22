from __future__ import annotations

import pytest

from cady.ops.triangulation import triangulate_float32


def test_triangulate_float32_fans_outer_ring() -> None:
    vertices = [0, 0, 1, 0, 1, 1, 0, 1]

    assert triangulate_float32(vertices) == [0, 1, 2, 0, 2, 3]


def test_triangulate_float32_rejects_unsupported_dimensions() -> None:
    with pytest.raises(ValueError, match="only 2D"):
        triangulate_float32([0, 0, 0, 1, 0, 0, 1, 1, 0], dimensions=3)


def test_triangulate_float32_rejects_holes() -> None:
    with pytest.raises(ValueError, match="hole indices"):
        triangulate_float32([0, 0, 1, 0, 1, 1, 0, 1], hole_indices=[4])
