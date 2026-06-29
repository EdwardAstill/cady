from __future__ import annotations

import numpy as np
import pytest

from cady.geometry import PointCloud2
from cady.operations.transforms import Transform2


def test_point_cloud_2_bounds_array_and_transform() -> None:
    cloud = PointCloud2(
        (
            (0.0, 0.0),
            (1.0, -2.0),
        )
    )

    assert cloud.vertices == ((0.0, 0.0), (1.0, -2.0))
    assert cloud.bounds() == ((0.0, -2.0), (1.0, 0.0))
    np.testing.assert_array_equal(
        cloud.to_array(tolerance=1e-3),
        [[0.0, 0.0], [1.0, -2.0]],
    )

    moved = cloud.transformed(Transform2(cloud.vertices).translate(0.0, 2.0))

    assert moved.vertices == ((0.0, 2.0), (1.0, 0.0))


def test_point_cloud_2_requires_positive_tolerance_for_array_conversion() -> None:
    cloud = PointCloud2(((0.0, 0.0),))

    with pytest.raises(ValueError, match="tolerance"):
        cloud.to_array(tolerance=0.0)
