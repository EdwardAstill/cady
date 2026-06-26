from __future__ import annotations

import pytest

from cady.geometry import Frame3D
from cady.operations.transforms import Transform3
from cady.vec import Vec3


def test_world_xy_frame_maps_local_points() -> None:
    frame = Frame3D.world_xy()

    assert frame.point(2.0, 3.0) == Vec3(2.0, 3.0, 0.0)
    assert frame.y_axis == Vec3(0.0, 1.0, 0.0)


def test_from_normal_projects_x_axis_onto_plane() -> None:
    frame = Frame3D.from_normal((1.0, 2.0, 3.0), (0.0, 0.0, 2.0), x_axis=(1.0, 0.0, 1.0))

    assert frame.origin == Vec3(1.0, 2.0, 3.0)
    assert frame.normal == Vec3(0.0, 0.0, 1.0)
    assert frame.x_axis == Vec3(1.0, 0.0, 0.0)


def test_frame_rejects_zero_normal() -> None:
    with pytest.raises(ValueError, match="normalise zero"):
        Frame3D.from_normal((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))


def test_transformed_frame_moves_origin_and_axes() -> None:
    frame = Frame3D.world_xy().transformed(Transform3.translation(1.0, 2.0, 3.0))

    assert frame.origin == Vec3(1.0, 2.0, 3.0)
    assert frame.point(2.0, 3.0) == Vec3(3.0, 5.0, 3.0)
