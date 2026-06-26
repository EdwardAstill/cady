from __future__ import annotations

import numpy as np
import pytest

from cady.geometry import PointCloud3D
from cady.operations.transforms import Transform3
from cady.vec import Vec3


def test_point_cloud_bounds_array_and_transform() -> None:
    cloud = PointCloud3D(
        (
            Vec3(0.0, 0.0, 0.0),
            (1.0, -2.0, 3.0),
        )
    )

    assert cloud.vertices == (Vec3(0.0, 0.0, 0.0), Vec3(1.0, -2.0, 3.0))
    assert cloud.bounds() == (Vec3(0.0, -2.0, 0.0), Vec3(1.0, 0.0, 3.0))
    np.testing.assert_array_equal(
        cloud.to_array(tolerance=1e-3),
        [[0.0, 0.0, 0.0], [1.0, -2.0, 3.0]],
    )

    moved = cloud.transformed(Transform3.translation(0.0, 0.0, 2.0))

    assert moved.vertices == (Vec3(0.0, 0.0, 2.0), Vec3(1.0, -2.0, 5.0))


def test_point_cloud_requires_positive_tolerance_for_array_conversion() -> None:
    cloud = PointCloud3D((Vec3(0.0, 0.0, 0.0),))

    with pytest.raises(ValueError, match="tolerance"):
        cloud.to_array(tolerance=0.0)
