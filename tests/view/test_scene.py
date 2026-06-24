from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from cady.product import Part
from cady.view import Camera, DirectionalLight, DisplayStyle, Scene, ViewError


def test_scene_stores_targets_and_view_state_immutably() -> None:
    part = Part("plate")
    camera = Camera.look_at(position=(1, -2, 3), target=(0, 0, 0))
    style = DisplayStyle(color=(0.1, 0.2, 0.3), opacity=0.8)

    scene = (
        Scene.from_target(part, name="part view")
        .add("drawing", name="front", style=style)
        .with_camera(camera, name="main")
        .with_light(DirectionalLight(direction=(-1, -1, -1)))
    )

    assert [obj.object_name for obj in scene.objects] == ["plate", "front"]
    assert scene.active_camera == "main"
    assert len(scene.lights) == 2

    with pytest.raises(FrozenInstanceError):
        scene.name = "changed"  # type: ignore[misc]


def test_scene_rejects_invalid_references() -> None:
    with pytest.raises(ViewError):
        Scene(active_camera="missing")
    with pytest.raises(ViewError):
        Scene().with_camera(Camera.look_at(position=(1, -2, 3), target=(0, 0, 0))).with_camera(
            Camera.look_at(position=(2, -3, 4), target=(0, 0, 0))
        )
    with pytest.raises(ViewError):
        Scene().add(None)


def test_display_style_validates_render_state() -> None:
    assert DisplayStyle(render_mode="wireframe").render_mode == "wireframe"
    with pytest.raises(ViewError):
        DisplayStyle(opacity=1.5)
    with pytest.raises(ViewError):
        DisplayStyle(render_mode="hidden")  # type: ignore[arg-type]
