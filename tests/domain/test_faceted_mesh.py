from __future__ import annotations

import pytest

from cady import Face3D, FacetedMesh, Polyline3D, Vec3
from cady.numeric import ArrayMesh3, ArrayPolyline3


def test_face3d_triangulates_quad_with_fan() -> None:
    face = Face3D(
        (
            Vec3(0, 0, 0),
            Vec3(1, 0, 0),
            Vec3(1, 1, 0),
            Vec3(0, 1, 0),
        )
    )

    assert face.triangles() == (
        (Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(1, 1, 0)),
        (Vec3(0, 0, 0), Vec3(1, 1, 0), Vec3(0, 1, 0)),
    )
    assert face.bounds() == (Vec3(0, 0, 0), Vec3(1, 1, 0))


def test_faceted_mesh_from_faces_deduplicates_vertices_and_converts_to_array() -> None:
    mesh = FacetedMesh.from_faces(
        (
            Face3D((Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(0, 1, 0))),
            Face3D((Vec3(0, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1))),
        )
    )

    array_mesh = mesh.to_array(tolerance=1e-3)

    assert mesh.vertices == (Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1))
    assert mesh.faces == ((0, 1, 2), (0, 2, 3))
    assert isinstance(array_mesh, ArrayMesh3)
    assert array_mesh.faces.shape == (2, 3)


def test_faceted_mesh_is_transformable_shape3d() -> None:
    mesh = FacetedMesh(
        (Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(0, 1, 0)),
        ((0, 1, 2),),
    )

    moved = mesh.translate(1, 2, 3)

    assert isinstance(moved, FacetedMesh)
    assert moved.bounds() == (Vec3(1, 2, 3), Vec3(2, 3, 3))


def test_polyline3d_converts_to_array_polyline() -> None:
    wire = Polyline3D((Vec3(0, 0, 0), Vec3(1, 0, 1)), closed=False)

    array_wire = wire.to_array(tolerance=1e-3)

    assert isinstance(array_wire, ArrayPolyline3)
    assert array_wire.vertices.shape == (2, 3)
    assert wire.bounds() == (Vec3(0, 0, 0), Vec3(1, 0, 1))


def test_faceted_domain_objects_validate_shape() -> None:
    with pytest.raises(ValueError, match="at least three vertices"):
        Face3D((Vec3(0, 0, 0), Vec3(1, 0, 0)))

    with pytest.raises(ValueError, match="faces must be triangles"):
        FacetedMesh((Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(0, 1, 0)), ((0, 1),))

    with pytest.raises(ValueError, match="out of range"):
        FacetedMesh((Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(0, 1, 0)), ((0, 1, 3),))
