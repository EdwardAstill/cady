from __future__ import annotations

import pytest

from cady.geometry import Plane3
from cady.operations.transforms import Transform3


def test_world_xy_frame_maps_local_points() -> None:
    plane = Plane3.world_xy()

    assert plane.point(2.0, 3.0) == (2.0, 3.0, 0.0)
    assert plane.y_axis == (0.0, 1.0, 0.0)


def test_from_normal_projects_x_axis_onto_plane() -> None:
    plane = Plane3.from_normal((1.0, 2.0, 3.0), (0.0, 0.0, 2.0), x_axis=(1.0, 0.0, 1.0))

    assert plane.origin == (1.0, 2.0, 3.0)
    assert plane.normal == (0.0, 0.0, 1.0)
    assert plane.x_axis == (1.0, 0.0, 0.0)


def test_plane_projects_points_to_local_coordinates() -> None:
    plane = Plane3.from_normal((1.0, 2.0, 3.0), (0.0, 0.0, 1.0))

    assert plane.coordinates((4.0, 6.0, 8.0)) == (3.0, 4.0)
    assert plane.signed_distance((4.0, 6.0, 8.0)) == 5.0
    assert plane.project((4.0, 6.0, 8.0)) == (4.0, 6.0, 3.0)


def test_plane_fit_returns_best_fit_projection_frame() -> None:
    plane = Plane3.fit(
        (
            (0.0, 0.0, 2.0),
            (1.0, 0.0, 2.0),
            (0.0, 1.0, 2.0),
            (1.0, 1.0, 2.0),
        )
    )

    assert plane.origin == (0.5, 0.5, 2.0)
    assert plane.normal == (0.0, 0.0, 1.0)
    assert plane.max_deviation(((0.0, 0.0, 2.0), (1.0, 1.0, 2.0))) == 0.0


def test_frame_rejects_zero_normal() -> None:
    with pytest.raises(ValueError, match="normalise zero"):
        Plane3.from_normal((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))


def test_transformed_frame_moves_origin_and_axes() -> None:
    plane = Plane3.world_xy().transformed(Transform3().translate(1.0, 2.0, 3.0))

    assert plane.origin == (1.0, 2.0, 3.0)
    assert plane.point(2.0, 3.0) == (3.0, 5.0, 3.0)
