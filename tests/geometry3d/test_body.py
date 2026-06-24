from __future__ import annotations

import numpy as np
import pytest

from cady.geometry3d import Body3D, Frame3D, box, cylinder, sphere
from cady.numeric.paths2d import ArrayPolygon2
from cady.numeric.transform import Transform3
from cady.vec import Vec3


class RectangleProfile:
    def __init__(self, width: float, depth: float) -> None:
        self.width = width
        self.depth = depth

    def to_array(self, *, tolerance: float) -> ArrayPolygon2:
        return ArrayPolygon2(
            (
                (0.0, 0.0),
                (self.width, 0.0),
                (self.width, self.depth),
                (0.0, self.depth),
            )
        )


def test_box_factory_meshes_to_expected_bounds_and_faces() -> None:
    mesh = box(2.0, 3.0, 4.0).to_mesh(tolerance=1e-3)

    assert mesh.bounds() == (Vec3(0.0, 0.0, 0.0), Vec3(2.0, 3.0, 4.0))
    assert len(mesh.vertices) == 8
    assert len(mesh.faces) == 12


def test_box_respects_frame() -> None:
    frame = Frame3D.from_normal((10.0, 0.0, 0.0), (0.0, 0.0, 1.0))

    mesh = Body3D.box(width=1.0, depth=2.0, height=3.0, frame=frame).to_mesh(tolerance=1e-3)

    assert mesh.bounds() == (Vec3(10.0, 0.0, 0.0), Vec3(11.0, 2.0, 3.0))


def test_cylinder_uses_tolerance_for_segment_count() -> None:
    coarse = cylinder(1.0, 2.0).to_mesh(tolerance=0.5)
    fine = cylinder(1.0, 2.0).to_mesh(tolerance=0.01)

    assert coarse.bounds()[0].z == 0.0
    assert coarse.bounds()[1].z == 2.0
    assert len(fine.faces) > len(coarse.faces)


def test_sphere_mesh_bounds_are_centred_on_requested_point() -> None:
    mesh = sphere(2.0, centre=(1.0, 2.0, 3.0)).to_mesh(tolerance=0.1)
    lower, upper = mesh.bounds()

    assert lower.z == pytest.approx(1.0)
    assert upper.z == pytest.approx(5.0)
    assert lower.x <= -0.9
    assert upper.x >= 2.9
    assert lower.y <= 0.1
    assert upper.y >= 3.9


def test_profile_extrusion_meshes_caps_and_sides() -> None:
    body = Body3D.from_profile(RectangleProfile(2.0, 3.0)).extrude(4.0)

    mesh = body.to_mesh(tolerance=1e-3)

    assert mesh.bounds() == (Vec3(0.0, 0.0, 0.0), Vec3(2.0, 3.0, 4.0))
    assert len(mesh.faces) == 12


def test_extrude_accepts_profile_directly() -> None:
    body = Body3D().extrude(2.0, profile=RectangleProfile(1.0, 1.0))

    assert body.to_mesh(tolerance=1e-3).bounds()[1] == Vec3(1.0, 1.0, 2.0)


def test_body_transform_applies_to_meshable_feature_frames() -> None:
    moved = box(1.0, 1.0, 1.0).transformed(Transform3.translation(3.0, 4.0, 5.0))

    assert moved.to_mesh(tolerance=1e-3).bounds() == (
        Vec3(3.0, 4.0, 5.0),
        Vec3(4.0, 5.0, 6.0),
    )


def test_profile_extrusion_requires_profile_like_object() -> None:
    with pytest.raises(TypeError, match="to_array"):
        Body3D().extrude(1.0, profile=object()).to_mesh(tolerance=1e-3)


def test_mesh_to_array_from_body() -> None:
    array = box(1.0, 1.0, 1.0).to_mesh(tolerance=1e-3).to_array(tolerance=1e-3)

    assert array.vertices.shape == (8, 3)
    np.testing.assert_array_equal(array.faces.shape, (12, 3))
