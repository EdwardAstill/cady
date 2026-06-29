from __future__ import annotations

import numpy as np
import pytest

from cady.operations.arrays import as_points2, as_points3


def test_points_validation_coerces_dtype() -> None:
    points2 = as_points2([(1, 2), (3, 4)])
    points3 = as_points3(((1, 2, 3), (4, 5, 6)))

    assert points2.dtype == np.float64
    assert points3.dtype == np.float64
    np.testing.assert_allclose(points2, [[1.0, 2.0], [3.0, 4.0]])
    np.testing.assert_allclose(points3, [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ([1.0, 2.0], "rank 2"),
        ([[1.0, 2.0, 3.0]], "shape \\(n, 2\\)"),
        ([[1.0, np.nan]], "finite"),
        ([[1.0, np.inf]], "finite"),
    ],
)
def test_points2_validation_rejects_invalid_arrays(value: object, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        as_points2(value)
