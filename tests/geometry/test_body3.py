from __future__ import annotations

from typing import TypeAlias

import numpy as np
import pytest
from numpy.typing import NDArray

from cady.geometry import Body3, Plane3
from cady.operations.transforms import Transform3

PointArray2: TypeAlias = NDArray[np.float64]


class RectangleRegion:
    def __init__(self, width: float, depth: float) -> None:
        self.width = width
        self.depth = depth

    @property
    def closed(self) -> bool:
        return True

    def to_array(self, *, tolerance: float) -> PointArray2:
        return np.array(
            (
                (0.0, 0.0),
                (self.width, 0.0),
                (self.width, self.depth),
                (0.0, self.depth),
            ),
            dtype=np.float64,
            copy=True,
        )


def test_box_constructor_meshes_to_expected_bounds_and_faces() -> None:
    mesh = Body3.box(width=2.0, depth=3.0, height=4.0).to_mesh(tolerance=1e-3)

    assert mesh.bounds() == ((0.0, 0.0, 0.0), (2.0, 3.0, 4.0))
    assert len(mesh.vertices) == 8
    assert len(mesh.faces) == 12


def test_box_respects_frame() -> None:
    plane = Plane3.from_normal((10.0, 0.0, 0.0), (0.0, 0.0, 1.0))

    mesh = Body3.box(width=1.0, depth=2.0, height=3.0, plane=plane).to_mesh(tolerance=1e-3)

    assert mesh.bounds() == ((10.0, 0.0, 0.0), (11.0, 2.0, 3.0))


def test_cylinder_uses_tolerance_for_segment_count() -> None:
    coarse = Body3.cylinder(radius=1.0, height=2.0).to_mesh(tolerance=0.5)
    fine = Body3.cylinder(radius=1.0, height=2.0).to_mesh(tolerance=0.01)

    assert coarse.bounds()[0][2] == 0.0
    assert coarse.bounds()[1][2] == 2.0
    assert len(fine.faces) > len(coarse.faces)


def test_sphere_mesh_bounds_are_centered_on_requested_point() -> None:
    mesh = Body3.sphere(radius=2.0, center=(1.0, 2.0, 3.0)).to_mesh(tolerance=0.1)
    lower, upper = mesh.bounds()

    assert lower[2] == pytest.approx(1.0)
    assert upper[2] == pytest.approx(5.0)
    assert lower[0] <= -0.9
    assert upper[0] >= 2.9
    assert lower[1] <= 0.1
    assert upper[1] >= 3.9


def test_region_extrusion_meshes_caps_and_sides() -> None:
    body = Body3.from_region(RectangleRegion(2.0, 3.0)).extrude(4.0)

    mesh = body.to_mesh(tolerance=1e-3)

    assert mesh.bounds() == ((0.0, 0.0, 0.0), (2.0, 3.0, 4.0))
    assert len(mesh.faces) == 12


def test_extrude_accepts_region_directly() -> None:
    body = Body3().extrude(2.0, region=RectangleRegion(1.0, 1.0))

    assert body.to_mesh(tolerance=1e-3).bounds()[1] == (1.0, 1.0, 2.0)


def test_body_transform_applies_to_meshable_feature_frames() -> None:
    moved = Body3.box(width=1.0, depth=1.0, height=1.0).transformed(
        Transform3().translate(3.0, 4.0, 5.0)
    )

    assert moved.to_mesh(tolerance=1e-3).bounds() == (
        (3.0, 4.0, 5.0),
        (4.0, 5.0, 6.0),
    )


def test_region_extrusion_requires_region_like_object() -> None:
    with pytest.raises(TypeError, match="to_array"):
        Body3().extrude(1.0, region=object()).to_mesh(tolerance=1e-3)


def test_mesh_to_array_from_body() -> None:
    vertices, faces, _edges = (
        Body3.box(width=1.0, depth=1.0, height=1.0)
        .to_mesh(tolerance=1e-3)
        .to_array(tolerance=1e-3)
    )

    assert vertices.shape == (8, 3)
    np.testing.assert_array_equal(faces.shape, (12, 3))
