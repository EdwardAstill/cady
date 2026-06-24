from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from cady.view import Camera, ViewError


def test_camera_look_at_normalises_tuple_values_and_is_frozen() -> None:
    camera = Camera.look_at(position=(1, -2, 3), target=(0, 0, 0))

    assert camera.position == (1.0, -2.0, 3.0)
    assert camera.target == (0.0, 0.0, 0.0)

    with pytest.raises(FrozenInstanceError):
        camera.target = (1.0, 1.0, 1.0)  # type: ignore[misc]


def test_camera_rejects_degenerate_views_and_invalid_projection_values() -> None:
    with pytest.raises(ViewError):
        Camera.look_at(position=(0, 0, 0), target=(0, 0, 0))
    with pytest.raises(ViewError):
        Camera(position=(0, 0, 1), target=(0, 0, 0), up=(0, 0, 1))
    with pytest.raises(ViewError):
        Camera.perspective(position=(0, -1, 1), target=(0, 0, 0), fov_degrees=181)
    with pytest.raises(ViewError):
        Camera.orthographic(position=(0, -1, 1), target=(0, 0, 0), scale=0)
