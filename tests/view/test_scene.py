from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from cady.product import Part
from cady.view import Camera, DirectionalLight, DisplayStyle, ScaleBarOverlay, Scene, ViewError
from cady.view.overlay import LocalAxesOverlay


def test_scene_stores_targets_and_view_state_immutably() -> None:
    part = Part("plate")
    camera = Camera.look_at(position=(1, -2, 3), target=(0, 0, 0))
    style = DisplayStyle(color=(0.1, 0.2, 0.3), opacity=0.8)

    scene = (
        Scene(
            "part view",
            camera=camera,
            lights=(DirectionalLight(direction=(-1, -1, -1)),),
        )
        .add(part)
        .add("drawing", name="front", style=style)
    )

    assert [obj.object_name for obj in scene.objects] == ["plate", "front"]
    assert scene.camera is camera
    assert len(scene.lights) == 1
    assert scene.overlays == ()

    with pytest.raises(FrozenInstanceError):
        scene.name = "changed"  # type: ignore[misc]


def test_scene_stores_overlay_values() -> None:
    scale_bar = ScaleBarOverlay(color=(0.1, 0.2, 0.3), min_pixels=20.0, max_pixels=80.0)
    local_axes = LocalAxesOverlay(visible=False)
    scene = Scene("review", overlays=(local_axes,)).with_overlay(scale_bar)

    assert scene.overlays == (local_axes, scale_bar)

    with pytest.raises(ViewError):
        ScaleBarOverlay(min_pixels=100.0, max_pixels=50.0)
    with pytest.raises(ViewError):
        Scene(overlays=(object(),))  # type: ignore[list-item]
    with pytest.raises(ViewError):
        Scene().with_overlay(object())


def test_scene_defaults_to_simple_lighting_without_overlays() -> None:
    scene = Scene()

    assert scene.overlays == ()
    assert [light.intensity for light in scene.lights] == [0.35, 0.65]


def test_local_axes_overlay_validates_axis_colors() -> None:
    overlay = LocalAxesOverlay(
        x_color=(1.0, 0.0, 0.0),
        y_color=(0.0, 1.0, 0.0),
        z_color=(0.0, 0.0, 1.0),
    )

    assert overlay.x_color == (1.0, 0.0, 0.0)
    assert overlay.y_color == (0.0, 1.0, 0.0)
    assert overlay.z_color == (0.0, 0.0, 1.0)

    with pytest.raises(ValueError):
        LocalAxesOverlay(x_color=(1.2, 0.0, 0.0))


def test_scene_view_uses_lazy_public_viewer(monkeypatch: pytest.MonkeyPatch) -> None:
    view = pytest.importorskip("cady.view")
    scene = Scene("review")
    opened: list[tuple[object, float, str | None]] = []

    def fake_view_scene(
        scene_arg: object,
        *,
        tolerance: float = 1e-3,
        title: str | None = None,
    ) -> None:
        opened.append((scene_arg, tolerance, title))

    monkeypatch.setattr(view, "view_scene", fake_view_scene)

    result = scene.view(tolerance=0.25, title="scene window")

    assert result is None
    assert opened == [(scene, 0.25, "scene window")]


def test_scene_rejects_invalid_references() -> None:
    with pytest.raises(ViewError):
        Scene(camera=object())  # type: ignore[arg-type]
    with pytest.raises(ViewError):
        Scene(lights=(object(),))  # type: ignore[list-item]
    with pytest.raises(ViewError):
        Scene().add(None)
    assert not hasattr(Scene(), "with_camera")
    assert not hasattr(Scene(), "with_light")


def test_display_style_validates_render_state() -> None:
    assert DisplayStyle(render_mode="wireframe").render_mode == "wireframe"
    with pytest.raises(ViewError):
        DisplayStyle(opacity=1.5)
    with pytest.raises(ViewError):
        DisplayStyle(render_mode="hidden")  # type: ignore[arg-type]
