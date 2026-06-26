from __future__ import annotations

import pytest

from cady.errors import GeometryError
from cady.geometry.mesh3d import Mesh3D
from cady.geometry.polyline3d import ClosedPolyline3D, Polyline3D
from cady.vec import Vec3


def _face_normal_z(mesh: Mesh3D, face: tuple[int, int, int]) -> float:
    a, b, c = (mesh.vertices[index] for index in face)
    ab = b - a
    ac = c - a
    return ab.cross(ac).z


def test_closed_polyline3d_planar_square_to_mesh() -> None:
    polyline = ClosedPolyline3D(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        )
    )

    mesh = polyline.to_mesh(tolerance=1e-3)

    assert isinstance(mesh, Mesh3D)
    assert mesh.vertices == (
        Vec3(0.0, 0.0, 0.0),
        Vec3(1.0, 0.0, 0.0),
        Vec3(1.0, 1.0, 0.0),
        Vec3(0.0, 1.0, 0.0),
    )
    assert len(mesh.faces) == 2
    assert mesh.edges == ((0, 1), (1, 2), (2, 3), (3, 0))
    assert all(_face_normal_z(mesh, face) > 0.0 for face in mesh.faces)


def test_closed_polyline3d_rejects_non_planar_loop() -> None:
    polyline = ClosedPolyline3D(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 1.0),
            (0.0, 1.0, 0.0),
        )
    )

    with pytest.raises(GeometryError, match="non-planar"):
        polyline.to_mesh(tolerance=1e-3)


def test_polyline3d_is_open_wire_data_without_to_mesh() -> None:
    polyline = Polyline3D(((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)))

    assert polyline.points() == (Vec3(0.0, 0.0, 0.0), Vec3(1.0, 0.0, 0.0))
    assert not hasattr(polyline, "to_mesh")


def test_closed_polyline3d_dedupes_repeated_final_vertex() -> None:
    polyline = ClosedPolyline3D(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0),
        )
    )

    assert polyline.vertices == (
        Vec3(0.0, 0.0, 0.0),
        Vec3(1.0, 0.0, 0.0),
        Vec3(0.0, 1.0, 0.0),
    )
    assert polyline.points() == (
        Vec3(0.0, 0.0, 0.0),
        Vec3(1.0, 0.0, 0.0),
        Vec3(0.0, 1.0, 0.0),
        Vec3(0.0, 0.0, 0.0),
    )
    assert len(polyline.to_mesh(tolerance=1e-3).vertices) == 3
