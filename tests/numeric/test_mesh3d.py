from __future__ import annotations

import numpy as np
import pytest

from cady.numeric.mesh3d import ArrayMesh3, ArrayPolyline3
from cady.numeric.transform import Transform3


def test_polyline3_bounds_and_transform() -> None:
    polyline = ArrayPolyline3([[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]])

    np.testing.assert_allclose(polyline.bounds()[1], [1.0, 2.0, 3.0])
    np.testing.assert_allclose(
        polyline.transformed(Transform3.translation(1.0, 0.0, -1.0)).vertices,
        [[1.0, 0.0, -1.0], [2.0, 2.0, 2.0]],
    )


def test_mesh_triangles_bounds_and_transform_keeps_faces() -> None:
    mesh = ArrayMesh3(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        [[0, 1, 2]],
    )

    assert mesh.triangles.shape == (1, 3, 3)
    np.testing.assert_allclose(mesh.bounds()[1], [1.0, 1.0, 0.0])

    transformed = mesh.transformed(Transform3.translation(0.0, 0.0, 1.0))
    np.testing.assert_array_equal(transformed.faces, mesh.faces)
    np.testing.assert_allclose(transformed.triangles[0, 0], [0.0, 0.0, 1.0])


def test_mesh_mirror_reflects_vertices_and_reverses_face_winding() -> None:
    mesh = ArrayMesh3(
        [[1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [1.0, 0.0, 1.0]],
        [[0, 1, 2]],
        [[0, 1]],
    )

    mirrored = mesh.mirror((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))

    np.testing.assert_allclose(
        mirrored.vertices,
        [[-1.0, 0.0, 0.0], [-1.0, 1.0, 0.0], [-1.0, 0.0, 1.0]],
    )
    np.testing.assert_array_equal(mirrored.faces, [[0, 2, 1]])
    np.testing.assert_array_equal(mirrored.edges, mesh.edges)


def test_mesh_rejects_out_of_range_faces() -> None:
    with pytest.raises(ValueError, match="outside"):
        ArrayMesh3([[0.0, 0.0, 0.0]], [[0, 1, 2]])


def test_mesh_merged_offsets_face_indices() -> None:
    first = ArrayMesh3(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        [[0, 1, 2]],
    )
    second = ArrayMesh3(
        [[0.0, 0.0, 1.0], [1.0, 0.0, 1.0], [0.0, 1.0, 1.0]],
        [[0, 1, 2]],
    )

    merged = ArrayMesh3.merged([first, second])

    assert merged.vertices.shape == (6, 3)
    np.testing.assert_array_equal(merged.faces, [[0, 1, 2], [3, 4, 5]])
