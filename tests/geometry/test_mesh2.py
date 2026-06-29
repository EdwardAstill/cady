from __future__ import annotations

import numpy as np
import pytest

from cady.geometry.mesh import Mesh2
from cady.operations.transforms import Transform2


def test_mesh_triangles_bounds_and_transform() -> None:
    mesh = Mesh2(
        ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
        ((0, 1, 2),),
    )

    assert mesh.triangles == (((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),)
    assert mesh.bounds() == ((0.0, 0.0), (1.0, 1.0))
    assert mesh.boundary == ((0.0, 0.0), (1.0, 1.0))
    assert len(mesh.boundary_loops) == 1

    moved = mesh.transformed(Transform2(mesh.vertices).translate(2.0, -1.0))
    assert moved.bounds() == ((2.0, -1.0), (3.0, 0.0))
    assert moved.faces == mesh.faces


def test_mesh_to_array_requires_explicit_positive_tolerance() -> None:
    mesh = Mesh2(((0.0, 0.0),), ())

    with pytest.raises(ValueError, match="tolerance"):
        mesh.to_array(tolerance=0.0)


def test_mesh_to_array_returns_raw_arrays() -> None:
    mesh = Mesh2(
        ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
        ((0, 1, 2),),
        ((0, 1), (1, 2), (0, 2)),
    )

    vertices, faces, edges = mesh.to_array(tolerance=1e-3)

    np.testing.assert_allclose(vertices, [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    np.testing.assert_array_equal(faces, [[0, 1, 2]])
    np.testing.assert_array_equal(edges, [[0, 1], [1, 2], [0, 2]])


def test_mesh_merged_offsets_faces_and_edges() -> None:
    first = Mesh2(
        ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
        ((0, 1, 2),),
        ((0, 1),),
    )
    second = Mesh2(
        ((2.0, 0.0), (3.0, 0.0), (2.0, 1.0)),
        ((0, 1, 2),),
        ((1, 2),),
    )

    merged = Mesh2.merged((first, second))
    vertices, _faces, _edges = merged.to_array(tolerance=1e-3)

    assert merged.faces == ((0, 1, 2), (3, 4, 5))
    assert merged.edges == ((0, 1), (4, 5))
    assert vertices.shape == (6, 2)


def test_mesh_rejects_invalid_faces_and_edges() -> None:
    with pytest.raises(ValueError, match="faces reference vertices outside"):
        Mesh2(((0.0, 0.0),), ((0, 1, 2),))

    with pytest.raises(ValueError, match="edges reference vertices outside"):
        Mesh2(((0.0, 0.0),), (), ((0, 1),))

    with pytest.raises(ValueError, match="exactly three"):
        Mesh2(((0.0, 0.0),), ((0, 0),))  # type: ignore[list-item]
