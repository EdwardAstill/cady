from __future__ import annotations

import pytest

from cady.view import AmbientLight, DirectionalLight, PointLight, ViewError


def test_lights_validate_color_intensity_and_vectors() -> None:
    ambient = AmbientLight(intensity=0.25, color=(1, 1, 1))
    directional = DirectionalLight(direction=(-1, -1, -2), intensity=2.0)
    point = PointLight(position=(1, 2, 3), range=10)

    assert ambient.intensity == 0.25
    assert directional.direction == (-1.0, -1.0, -2.0)
    assert point.position == (1.0, 2.0, 3.0)

    with pytest.raises(ViewError):
        AmbientLight(intensity=-1)
    with pytest.raises(ViewError):
        DirectionalLight(direction=(0, 0, 0))
    with pytest.raises(ViewError):
        PointLight(range=0)
