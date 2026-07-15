from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from typing import TypeAlias

import numpy as np
import pytest
from numpy.typing import NDArray

from cady.geometry import Body3, Circle2, Plane3, Region2
from cady.geometry.body3 import (
    BooleanFeature,
    ChamferFeature,
    FilletFeature,
    RevolveFeature,
)
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


@pytest.mark.parametrize("tolerance", [0.0, -1.0, float("inf"), float("nan")])
def test_body_to_mesh_requires_positive_finite_tolerance(tolerance: float) -> None:
    body = Body3.box(width=1.0, depth=1.0, height=1.0)

    with pytest.raises(ValueError, match="tolerance"):
        body.to_mesh(tolerance=tolerance)


@pytest.mark.parametrize(
    ("constructor", "message"),
    (
        (lambda: Body3.box(width=0.0, depth=1.0, height=1.0), "width must be positive"),
        (lambda: Body3.box(width=1.0, depth=-1.0, height=1.0), "depth must be positive"),
        (lambda: Body3.box(width=1.0, depth=1.0, height=float("inf")), "height must be finite"),
        (lambda: Body3.cylinder(radius=0.0, height=1.0), "radius must be positive"),
        (lambda: Body3.cylinder(radius=1.0, height=-1.0), "height must be positive"),
        (lambda: Body3.sphere(radius=float("nan")), "radius must be finite"),
    ),
)
def test_primitive_dimensions_are_validated_at_construction(
    constructor: Callable[[], Body3],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        constructor()


def test_region_extrusion_meshes_caps_and_sides() -> None:
    body = Body3.from_region(RectangleRegion(2.0, 3.0)).extrude(4.0)

    mesh = body.to_mesh(tolerance=1e-3)

    assert mesh.bounds() == ((0.0, 0.0, 0.0), (2.0, 3.0, 4.0))
    assert len(mesh.faces) == 12


def test_region_extrusion_with_hole_keeps_cap_faces() -> None:
    outer = Region2.rectangle(1.0, 0.6).outer
    region = Region2(outer, holes=(Circle2((0.5, 0.3), 0.12),))

    mesh = Body3.from_region(region).extrude(0.04).to_mesh(tolerance=1e-3)
    vertices, faces, _edges = mesh.to_array(tolerance=1e-3)
    triangles = vertices[faces]
    normals = np.cross(
        triangles[:, 1] - triangles[:, 0],
        triangles[:, 2] - triangles[:, 0],
    )
    edge_counts: Counter[
        tuple[tuple[float, float, float], tuple[float, float, float]]
    ] = Counter()
    for face in mesh.faces:
        points = [tuple(round(value, 12) for value in mesh.vertices[index]) for index in face]
        for start, end in zip(points, points[1:] + points[:1], strict=True):
            edge_counts[tuple(sorted((start, end)))] += 1

    assert np.count_nonzero(np.abs(normals[:, 2]) > 1e-12) > 0
    assert set(edge_counts.values()) == {2}


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
        Body3().extrude(1.0, region=object())

    with pytest.raises(TypeError, match="to_array"):
        Body3.from_region(object())


def test_body_feature_planes_are_validated_at_construction() -> None:
    with pytest.raises(TypeError, match="feature plane must be a Plane3"):
        Body3.from_region(RectangleRegion(1.0, 1.0), plane=object())  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="feature plane must be a Plane3"):
        Body3.box(  # type: ignore[arg-type]
            width=1.0,
            depth=1.0,
            height=1.0,
            plane=object(),
        )


def test_body_rejects_unknown_feature_at_construction() -> None:
    with pytest.raises(TypeError, match="unsupported feature object"):
        Body3(features=(object(),))  # type: ignore[arg-type]


def test_body_rejects_second_generator_with_part_guidance() -> None:
    with pytest.raises(ValueError, match=r"Part\.with_bodies"):
        Body3.box(width=1.0, depth=1.0, height=1.0).extrude(
            1.0,
            region=RectangleRegion(1.0, 1.0),
        )


def test_empty_and_region_only_bodies_remain_unmeshable() -> None:
    for body in (Body3(), Body3.from_region(RectangleRegion(1.0, 1.0))):
        with pytest.raises(ValueError, match="body has no meshable features"):
            body.to_mesh(tolerance=1e-3)


def test_body_rejects_modifier_without_generator() -> None:
    with pytest.raises(ValueError, match="body modifier requires a solid generator"):
        Body3().with_feature(FilletFeature(0.1))


@pytest.mark.parametrize(
    ("body", "operation"),
    (
        (
            Body3(
                features=(
                    RevolveFeature(RectangleRegion(1.0, 1.0), Plane3.world_xy(), 180.0),
                )
            ),
            "revolve",
        ),
        (
            Body3.box(width=1.0, depth=1.0, height=1.0).with_feature(
                BooleanFeature("union", object())
            ),
            "boolean",
        ),
        (
            Body3.box(width=1.0, depth=1.0, height=1.0).with_feature(
                FilletFeature(0.1)
            ),
            "fillet",
        ),
        (
            Body3.box(width=1.0, depth=1.0, height=1.0).with_feature(
                ChamferFeature(0.1)
            ),
            "chamfer",
        ),
    ),
)
def test_unsupported_features_name_the_operation(body: Body3, operation: str) -> None:
    with pytest.raises(NotImplementedError, match=operation):
        body.to_mesh(tolerance=1e-3)


def test_mesh_to_array_from_body() -> None:
    vertices, faces, _edges = (
        Body3.box(width=1.0, depth=1.0, height=1.0)
        .to_mesh(tolerance=1e-3)
        .to_array(tolerance=1e-3)
    )

    assert vertices.shape == (8, 3)
    np.testing.assert_array_equal(faces.shape, (12, 3))
