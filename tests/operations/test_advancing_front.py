from __future__ import annotations

import numpy as np

from cady.operations.surface_reconstruction import advancing_front_surface


def test_advancing_front_returns_mesh_arrays() -> None:
    points = np.asarray(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
        ),
        dtype=np.float64,
    )

    vertices, faces, edges = advancing_front_surface(points, tolerance=1e-9)

    np.testing.assert_array_equal(vertices, points)
    np.testing.assert_array_equal(faces, np.asarray(((0, 1, 2),), dtype=np.int64))
    np.testing.assert_array_equal(edges, np.asarray(((0, 1), (0, 2), (1, 2)), dtype=np.int64))
