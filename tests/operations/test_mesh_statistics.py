from __future__ import annotations

from math import sqrt

import numpy as np
import pytest

from cady.geometry import Mesh2, Mesh3
from cady.operations.mesh.statistics import face_areas, radius_ratios


def test_face_areas_returns_one_area_per_coordinate_triangle() -> None:
    faces = np.array(
        [
            [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            [[0.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 2.0]],
        ],
        dtype=np.float64,
    )

    np.testing.assert_allclose(face_areas(faces), [1.0, 3.0])


def test_radius_ratios_accepts_coordinate_triangles_and_side_lengths() -> None:
    triangles = np.array(
        [
            [[0.0, 0.0], [1.0, 0.0], [0.5, sqrt(3.0) / 2.0]],
            [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]],
        ],
        dtype=np.float64,
    )
    lengths = np.array(
        [
            [1.0, 1.0, 1.0],
            [1.0, sqrt(2.0), 1.0],
        ],
        dtype=np.float64,
    )

    expected = [1.0, (1.0 + sqrt(2.0)) / 2.0]
    np.testing.assert_allclose(radius_ratios(triangles), expected)
    np.testing.assert_allclose(radius_ratios(lengths), expected)


def test_mesh2_statistics_methods_return_numpy_arrays() -> None:
    mesh = Mesh2(
        ((0.0, 0.0), (1.0, 0.0), (0.5, sqrt(3.0) / 2.0)),
        ((0, 1, 2),),
    )

    areas = mesh.face_areas()
    ratios = mesh.radius_ratios()

    assert isinstance(areas, np.ndarray)
    assert isinstance(ratios, np.ndarray)
    np.testing.assert_allclose(areas, [sqrt(3.0) / 4.0])
    np.testing.assert_allclose(ratios, [1.0])


def test_mesh3_statistics_methods_use_triangulated_faces() -> None:
    mesh = Mesh3(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ),
        ((0, 1, 2, 3),),
    )

    areas = mesh.face_areas()
    ratios = mesh.radius_ratios()

    assert areas.shape == (2,)
    assert ratios.shape == (2,)
    assert float(np.sum(areas)) == pytest.approx(1.0)
    np.testing.assert_allclose(ratios, [(1.0 + sqrt(2.0)) / 2.0] * 2)


def test_statistics_rejects_non_triangle_coordinate_faces() -> None:
    with pytest.raises(ValueError, match="faces must have shape"):
        face_areas(np.zeros((2, 4, 3), dtype=np.float64))
