from __future__ import annotations

import numpy as np
import pytest

from cady.geometry.mesh2d import Mesh2D
from cady.operations.transforms import Transform2
from cady.vec import Vec2


def test_mesh_triangles_bounds_and_transform() -> None:
    mesh = Mesh2D(
        (Vec2(0.0, 0.0), Vec2(1.0, 0.0), Vec2(0.0, 1.0)),
        ((0, 1, 2),),
    )

    assert mesh.triangles == ((Vec2(0.0, 0.0), Vec2(1.0, 0.0), Vec2(0.0, 1.0)),)
    assert mesh.bounds() == (Vec2(0.0, 0.0), Vec2(1.0, 1.0))

    moved = mesh.transformed(Transform2.translation(2.0, -1.0))
    assert moved.bounds() == (Vec2(2.0, -1.0), Vec2(3.0, 0.0))
    assert moved.faces == mesh.faces


def test_mesh_to_array_requires_explicit_positive_tolerance() -> None:
    mesh = Mesh2D((Vec2(0.0, 0.0),), ())

    with pytest.raises(ValueError, match="tolerance"):
        mesh.to_array(tolerance=0.0)


def test_mesh_to_array_returns_raw_arrays() -> None:
    mesh = Mesh2D(
        (Vec2(0.0, 0.0), Vec2(1.0, 0.0), Vec2(0.0, 1.0)),
        ((0, 1, 2),),
        ((0, 1), (1, 2), (0, 2)),
    )

    vertices, faces, edges = mesh.to_array(tolerance=1e-3)

    np.testing.assert_allclose(vertices, [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    np.testing.assert_array_equal(faces, [[0, 1, 2]])
    np.testing.assert_array_equal(edges, [[0, 1], [1, 2], [0, 2]])


def test_mesh_merged_offsets_faces_and_edges() -> None:
    first = Mesh2D(
        (Vec2(0.0, 0.0), Vec2(1.0, 0.0), Vec2(0.0, 1.0)),
        ((0, 1, 2),),
        ((0, 1),),
    )
    second = Mesh2D(
        (Vec2(2.0, 0.0), Vec2(3.0, 0.0), Vec2(2.0, 1.0)),
        ((0, 1, 2),),
        ((1, 2),),
    )

    merged = Mesh2D.merged((first, second))
    vertices, _faces, _edges = merged.to_array(tolerance=1e-3)

    assert merged.faces == ((0, 1, 2), (3, 4, 5))
    assert merged.edges == ((0, 1), (4, 5))
    assert vertices.shape == (6, 2)


def test_mesh_rejects_invalid_faces_and_edges() -> None:
    with pytest.raises(ValueError, match="faces reference vertices outside"):
        Mesh2D((Vec2(0.0, 0.0),), ((0, 1, 2),))

    with pytest.raises(ValueError, match="edges reference vertices outside"):
        Mesh2D((Vec2(0.0, 0.0),), (), ((0, 1),))

    with pytest.raises(ValueError, match="exactly three"):
        Mesh2D((Vec2(0.0, 0.0),), ((0, 0),))  # type: ignore[list-item]
