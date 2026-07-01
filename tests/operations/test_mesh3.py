from __future__ import annotations

import numpy as np
import pytest

from cady.errors import GeometryError
from cady.geometry import Mesh3
from cady.operations.mesh_topology import decimate_mesh_data
from cady.operations.transforms import Transform3


def test_polyline3_bounds_and_transform() -> None:
    polyline = np.array([[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]], dtype=np.float64)

    np.testing.assert_allclose(np.max(polyline, axis=0), [1.0, 2.0, 3.0])
    np.testing.assert_allclose(
        Transform3().translate(1.0, 0.0, -1.0).apply_points(polyline),
        [[1.0, 0.0, -1.0], [2.0, 2.0, 2.0]],
    )


def test_mesh_triangles_bounds_and_transform_keeps_faces() -> None:
    mesh = Mesh3(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
    )

    assert len(mesh.triangles) == 1
    assert mesh.bounds()[1] == (1.0, 1.0, 0.0)
    assert mesh.boundary == ((0.0, 0.0, 0.0), (1.0, 1.0, 0.0))

    transformed = mesh.transformed(Transform3().translate(0.0, 0.0, 1.0))
    assert transformed.faces == mesh.faces
    assert transformed.triangles[0][0] == (0.0, 0.0, 1.0)


def test_mesh_boundary_loops_returns_closed_polyline3() -> None:
    mesh = Mesh3(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
    )

    boundary = mesh.boundary_loops[0]

    assert isinstance(boundary, np.ndarray)
    assert boundary.shape == (4, 3)
    np.testing.assert_allclose(boundary[0], boundary[-1])
    assert {tuple(row) for row in boundary[:-1]} == {
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    }
    assert len(mesh.boundary_loops) == 1


def test_mesh_boundary_loops_raises_when_mesh_has_no_faces() -> None:
    mesh = Mesh3(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        (),
        ((0, 1),),
    )

    assert mesh.boundary == ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))

    with pytest.raises(GeometryError, match="no faces"):
        _ = mesh.boundary_loops


def test_mesh_boundary_loops_returns_empty_tuple_when_mesh_is_closed() -> None:
    mesh = Mesh3(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
        ),
        ((0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3)),
    )

    assert mesh.boundary_loops == ()


def test_mesh_boundary_loops_raises_for_non_manifold_edges() -> None:
    mesh = Mesh3(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, -1.0, 0.0),
            (0.0, 0.0, 1.0),
        ),
        ((0, 1, 2), (1, 0, 3), (0, 1, 4)),
    )

    with pytest.raises(GeometryError, match="non-manifold"):
        _ = mesh.boundary_loops


def test_mesh_mirror_reflects_vertices_and_reverses_face_winding() -> None:
    mesh = Mesh3(
        ((1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (1.0, 0.0, 1.0)),
        ((0, 1, 2),),
        ((0, 1),),
    )

    mirrored = mesh.mirror((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))

    assert mirrored.vertices == (
        (-1.0, 0.0, 0.0),
        (-1.0, 1.0, 0.0),
        (-1.0, 0.0, 1.0),
    )
    assert mirrored.faces == ((0, 2, 1),)
    assert mirrored.edges == mesh.edges


def test_mesh_rejects_out_of_range_faces() -> None:
    with pytest.raises(ValueError, match="outside"):
        Mesh3(((0.0, 0.0, 0.0),), ((0, 1, 2),))


def test_mesh_merged_offsets_face_indices() -> None:
    first = Mesh3(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
    )
    second = Mesh3(
        ((0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (0.0, 1.0, 1.0)),
        ((0, 1, 2),),
    )

    merged = Mesh3.merged([first, second])

    assert len(merged.vertices) == 6
    assert merged.faces == ((0, 1, 2), (3, 4, 5))


def test_decimate_mesh_data_collapses_short_edges_to_target() -> None:
    vertices = np.array(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (1.0, 1.0, 0.0),
            (2.0, 1.0, 0.0),
            (0.0, 2.0, 0.0),
            (1.0, 2.0, 0.0),
            (2.0, 2.0, 0.0),
        ],
        dtype=np.float64,
    )
    faces = np.array(
        [
            (0, 1, 4),
            (0, 4, 3),
            (1, 2, 5),
            (1, 5, 4),
            (3, 4, 7),
            (3, 7, 6),
            (4, 5, 8),
            (4, 8, 7),
        ],
        dtype=np.int64,
    )
    edges = np.array([(0, 1), (1, 2), (2, 5)], dtype=np.int64)

    out_vertices, out_faces, out_edges = decimate_mesh_data(
        vertices,
        faces,
        edges,
        target_faces=4,
        tolerance=1e-9,
    )

    assert out_vertices.dtype == np.float64
    assert out_faces.dtype == np.int64
    assert out_edges.dtype == np.int64
    assert out_vertices.shape[1] == 3
    assert out_faces.shape[1] == 3
    assert out_edges.shape[1] == 2
    assert len(out_faces) <= 4
    assert len(out_vertices) < len(vertices)
    assert int(np.max(out_faces)) < len(out_vertices)
