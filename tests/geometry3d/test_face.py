from __future__ import annotations

from cady.geometry import Face3D
from cady.operations.arrays2d import ArrayPolygon2
from cady.vec import Vec3


class TriangleProfile:
    def to_array(self, *, tolerance: float) -> ArrayPolygon2:
        return ArrayPolygon2(((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)))


def test_face_from_profile_meshes_single_planar_cap() -> None:
    mesh = Face3D.from_profile(TriangleProfile()).to_mesh(tolerance=1e-3)

    assert len(mesh.faces) == 1
    assert mesh.bounds() == (Vec3(0.0, 0.0, 0.0), Vec3(1.0, 1.0, 0.0))


def test_face_from_points_projects_ordered_loop() -> None:
    face = Face3D.from_points(
        (
            (0.0, 0.0, 2.0),
            (1.0, 0.0, 2.0),
            (0.0, 1.0, 2.0),
        )
    )

    assert face.to_mesh(tolerance=1e-3).bounds() == (
        Vec3(0.0, 0.0, 2.0),
        Vec3(1.0, 1.0, 2.0),
    )


def test_face_convex_hull_discards_inner_points() -> None:
    face = Face3D.convex_hull(
        (
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (1.0, 0.5, 0.0),
            (2.0, 2.0, 0.0),
            (0.0, 2.0, 0.0),
        )
    )

    mesh = face.to_mesh(tolerance=1e-3)
    assert mesh.bounds() == (Vec3(0.0, 0.0, 0.0), Vec3(2.0, 2.0, 0.0))
