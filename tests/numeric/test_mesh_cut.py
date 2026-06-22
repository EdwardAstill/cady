from __future__ import annotations

from collections import Counter
from math import isclose

import numpy as np
import pytest

from cady.numeric.mesh3d import ArrayMesh3
from cady.ops import cut_mesh_by_plane


def unit_cube_mesh() -> ArrayMesh3:
    return ArrayMesh3(
        np.array(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [1.0, 1.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
                [1.0, 0.0, 1.0],
                [1.0, 1.0, 1.0],
                [0.0, 1.0, 1.0],
            ],
            dtype=np.float64,
        ),
        np.array(
            [
                [0, 2, 1],
                [0, 3, 2],
                [4, 5, 6],
                [4, 6, 7],
                [0, 1, 5],
                [0, 5, 4],
                [1, 2, 6],
                [1, 6, 5],
                [2, 3, 7],
                [2, 7, 6],
                [3, 0, 4],
                [3, 4, 7],
            ],
            dtype=np.int64,
        ),
    )


def mesh_volume(mesh: ArrayMesh3) -> float:
    volume = 0.0
    for triangle in mesh.triangles:
        volume += float(np.dot(triangle[0], np.cross(triangle[1], triangle[2]))) / 6.0
    return abs(volume)


def edge_counts(mesh: ArrayMesh3) -> Counter[tuple[int, int]]:
    counts: Counter[tuple[int, int]] = Counter()
    for face in mesh.faces:
        indices = [int(face[0]), int(face[1]), int(face[2])]
        for start, end in zip(indices, indices[1:] + indices[:1], strict=True):
            counts[(min(start, end), max(start, end))] += 1
    return counts


def test_cut_mesh_by_plane_caps_negative_side() -> None:
    clipped = cut_mesh_by_plane(
        unit_cube_mesh(),
        plane_origin=(0.0, 0.0, 0.5),
        plane_normal=(0.0, 0.0, 1.0),
        keep="negative",
    )

    lower, upper = clipped.bounds()
    np.testing.assert_allclose(lower, [0.0, 0.0, 0.0])
    np.testing.assert_allclose(upper, [1.0, 1.0, 0.5])
    assert isclose(mesh_volume(clipped), 0.5, rel_tol=1e-12, abs_tol=1e-12)
    assert set(edge_counts(clipped).values()) == {2}


def test_cut_mesh_by_plane_caps_positive_side() -> None:
    clipped = cut_mesh_by_plane(
        unit_cube_mesh(),
        plane_origin=(0.0, 0.0, 0.5),
        plane_normal=(0.0, 0.0, 1.0),
        keep="positive",
    )

    lower, upper = clipped.bounds()
    np.testing.assert_allclose(lower, [0.0, 0.0, 0.5])
    np.testing.assert_allclose(upper, [1.0, 1.0, 1.0])
    assert isclose(mesh_volume(clipped), 0.5, rel_tol=1e-12, abs_tol=1e-12)
    assert set(edge_counts(clipped).values()) == {2}


def test_cut_mesh_by_plane_without_cap_leaves_open_boundary() -> None:
    clipped = cut_mesh_by_plane(
        unit_cube_mesh(),
        plane_origin=(0.0, 0.0, 0.5),
        plane_normal=(0.0, 0.0, 1.0),
        keep="negative",
        cap=False,
    )

    np.testing.assert_allclose(clipped.bounds()[1], [1.0, 1.0, 0.5])
    assert 1 in set(edge_counts(clipped).values())


def test_cut_mesh_by_plane_does_not_duplicate_existing_plane_face() -> None:
    clipped = cut_mesh_by_plane(
        unit_cube_mesh(),
        plane_origin=(0.0, 0.0, 0.0),
        plane_normal=(0.0, 0.0, 1.0),
        keep="positive",
    )

    assert isclose(mesh_volume(clipped), 1.0, rel_tol=1e-12, abs_tol=1e-12)
    assert set(edge_counts(clipped).values()) == {2}


def test_cut_mesh_by_plane_returns_empty_mesh_when_fully_removed() -> None:
    clipped = cut_mesh_by_plane(
        unit_cube_mesh(),
        plane_origin=(0.0, 0.0, 2.0),
        plane_normal=(0.0, 0.0, 1.0),
        keep="positive",
    )

    assert clipped.vertices.shape == (0, 3)
    assert clipped.faces.shape == (0, 3)


def test_cut_mesh_by_plane_rejects_invalid_keep() -> None:
    with pytest.raises(ValueError, match="keep"):
        cut_mesh_by_plane(
            unit_cube_mesh(),
            plane_origin=(0.0, 0.0, 0.5),
            plane_normal=(0.0, 0.0, 1.0),
            keep="sideways",  # type: ignore[arg-type]
        )
