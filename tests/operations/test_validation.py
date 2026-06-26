from __future__ import annotations

import numpy as np
import pytest

from cady.operations.validation import as_faces, as_matrix3, as_matrix4, as_points2, as_points3


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


def test_faces_validation_coerces_dtype_and_rejects_bad_values() -> None:
    faces = as_faces([[0, 1, 2], [2.0, 3.0, 0.0]])

    assert faces.dtype == np.int64
    np.testing.assert_array_equal(faces, [[0, 1, 2], [2, 3, 0]])

    with pytest.raises(ValueError, match="shape"):
        as_faces([[0, 1]])
    with pytest.raises(ValueError, match="finite"):
        as_faces([[0, 1, np.nan]])
    with pytest.raises(ValueError, match="integer"):
        as_faces([[0.5, 1, 2]])


def test_matrix_validation_checks_exact_shape_and_dtype() -> None:
    matrix3 = as_matrix3(np.eye(3, dtype=np.int64))
    matrix4 = as_matrix4(np.eye(4).tolist())

    assert matrix3.dtype == np.float64
    assert matrix4.dtype == np.float64

    with pytest.raises(ValueError, match="shape"):
        as_matrix3(np.eye(4))
    with pytest.raises(ValueError, match="finite"):
        as_matrix4(np.full((4, 4), np.inf))

