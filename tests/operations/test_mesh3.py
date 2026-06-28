from __future__ import annotations

import numpy as np
import pytest

from cady.errors import GeometryError
from cady.geometry import Mesh3
from cady.operations.arrays3 import ArrayPolyline3
from cady.operations.transforms import Transform3
from cady.vec import Vec3


def test_polyline3_bounds_and_transform() -> None:
    polyline = ArrayPolyline3([[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]])

    np.testing.assert_allclose(polyline.bounds()[1], [1.0, 2.0, 3.0])
    np.testing.assert_allclose(
        polyline.transformed(Transform3.translation(1.0, 0.0, -1.0)).vertices,
        [[1.0, 0.0, -1.0], [2.0, 2.0, 2.0]],
    )


def test_mesh_triangles_bounds_and_transform_keeps_faces() -> None:
    mesh = Mesh3(
        (Vec3(0.0, 0.0, 0.0), Vec3(1.0, 0.0, 0.0), Vec3(0.0, 1.0, 0.0)),
        ((0, 1, 2),),
    )

    assert len(mesh.triangles) == 1
    assert mesh.bounds()[1] == Vec3(1.0, 1.0, 0.0)

    transformed = mesh.transformed(Transform3.translation(0.0, 0.0, 1.0))
    assert transformed.faces == mesh.faces
    assert transformed.triangles[0][0] == Vec3(0.0, 0.0, 1.0)


def test_mesh_boundary_returns_closed_polyline3() -> None:
    mesh = Mesh3(
        (Vec3(0.0, 0.0, 0.0), Vec3(1.0, 0.0, 0.0), Vec3(0.0, 1.0, 0.0)),
        ((0, 1, 2),),
    )

    boundary = mesh.boundary

    assert isinstance(boundary, ArrayPolyline3)
    assert boundary.vertices.shape == (4, 3)
    np.testing.assert_allclose(boundary.vertices[0], boundary.vertices[-1])
    assert {tuple(row) for row in boundary.vertices[:-1]} == {
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    }
    loops = mesh.boundary_loops
    assert len(loops) == 1
    np.testing.assert_allclose(loops[0].vertices, boundary.vertices)


def test_mesh_boundary_raises_when_mesh_has_no_faces() -> None:
    mesh = Mesh3(
        (Vec3(0.0, 0.0, 0.0), Vec3(1.0, 0.0, 0.0)),
        (),
        ((0, 1),),
    )

    with pytest.raises(GeometryError, match="no faces"):
        _ = mesh.boundary

    with pytest.raises(GeometryError, match="no faces"):
        _ = mesh.boundary_loops


def test_mesh_boundary_loops_returns_empty_tuple_when_mesh_is_closed() -> None:
    mesh = Mesh3(
        (
            Vec3(0.0, 0.0, 0.0),
            Vec3(1.0, 0.0, 0.0),
            Vec3(0.0, 1.0, 0.0),
            Vec3(0.0, 0.0, 1.0),
        ),
        ((0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3)),
    )

    assert mesh.boundary_loops == ()


def test_mesh_boundary_loops_raises_for_non_manifold_edges() -> None:
    mesh = Mesh3(
        (
            Vec3(0.0, 0.0, 0.0),
            Vec3(1.0, 0.0, 0.0),
            Vec3(0.0, 1.0, 0.0),
            Vec3(0.0, -1.0, 0.0),
            Vec3(0.0, 0.0, 1.0),
        ),
        ((0, 1, 2), (1, 0, 3), (0, 1, 4)),
    )

    with pytest.raises(GeometryError, match="non-manifold"):
        _ = mesh.boundary_loops


def test_mesh_mirror_reflects_vertices_and_reverses_face_winding() -> None:
    mesh = Mesh3(
        (Vec3(1.0, 0.0, 0.0), Vec3(1.0, 1.0, 0.0), Vec3(1.0, 0.0, 1.0)),
        ((0, 1, 2),),
        ((0, 1),),
    )

    mirrored = mesh.mirror((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))

    assert mirrored.vertices == (
        Vec3(-1.0, 0.0, 0.0),
        Vec3(-1.0, 1.0, 0.0),
        Vec3(-1.0, 0.0, 1.0),
    )
    assert mirrored.faces == ((0, 2, 1),)
    assert mirrored.edges == mesh.edges


def test_mesh_rejects_out_of_range_faces() -> None:
    with pytest.raises(ValueError, match="outside"):
        Mesh3((Vec3(0.0, 0.0, 0.0),), ((0, 1, 2),))


def test_mesh_merged_offsets_face_indices() -> None:
    first = Mesh3(
        (Vec3(0.0, 0.0, 0.0), Vec3(1.0, 0.0, 0.0), Vec3(0.0, 1.0, 0.0)),
        ((0, 1, 2),),
    )
    second = Mesh3(
        (Vec3(0.0, 0.0, 1.0), Vec3(1.0, 0.0, 1.0), Vec3(0.0, 1.0, 1.0)),
        ((0, 1, 2),),
    )

    merged = Mesh3.merged([first, second])

    assert len(merged.vertices) == 6
    assert merged.faces == ((0, 1, 2), (3, 4, 5))
