from __future__ import annotations

from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from cady.geometry import (
    Arc2,
    Arc3,
    Circle2,
    Ellipse2,
    Line2,
    Line3,
    Polyline2,
    Polyline3,
    Spline2,
    Spline3,
)
from cady.product import Part
from cady.view import Camera, DirectionalLight, DisplayStyle, ScaleBarOverlay, Scene, ViewError
from cady.view.overlay import LocalAxesOverlay
from cady.view.scene import prepare_scene


@pytest.mark.parametrize(
    "curve",
    [
        Line2((0.0, 0.0), (1.0, 2.0)),
        Line3((0.0, 0.0, 1.0), (1.0, 2.0, 3.0)),
        Arc2((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
        Arc3((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        Spline2(((0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0))),
        Spline2(
            ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
            closed=True,
        ),
        Spline3(
            (
                (0.0, 0.0, 0.0),
                (0.0, 1.0, 1.0),
                (1.0, 1.0, 1.0),
                (1.0, 0.0, 0.0),
            )
        ),
        Polyline2(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0))),
        Polyline2(
            ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0)),
            closed=True,
        ),
        Polyline3(
            ((0.0, 0.0, 0.0), (1.0, 0.0, 1.0), (1.0, 1.0, 1.0))
        ),
        Polyline3(
            ((0.0, 0.0, 0.0), (1.0, 0.0, 1.0), (1.0, 1.0, 1.0)),
            closed=True,
        ),
        Circle2((0.0, 0.0), 1.0),
        Ellipse2((0.0, 0.0), 2.0, 1.0),
    ],
    ids=[
        "line2",
        "line3",
        "arc2",
        "arc3",
        "spline2-open",
        "spline2-closed",
        "spline3",
        "polyline2-open",
        "polyline2-closed",
        "polyline3-open",
        "polyline3-closed",
        "circle2",
        "ellipse2",
    ],
)
def test_prepare_scene_accepts_semantic_curves(curve: object) -> None:
    scene = Scene("curves").add(curve)

    prepared = prepare_scene(scene, tolerance=1e-2)

    assert scene.objects[0].target is curve
    assert prepared.meshes == ()
    assert len(prepared.lines) == 1
    assert len(prepared.lines[0].vertices) >= 2
    assert len(prepared.lines[0].indices) >= 1
    assert prepared.lines[0].vertices.shape[1] == 3
    assert prepared.lines[0].vertices.dtype == np.float32
    assert prepared.lines[0].vertices.flags.c_contiguous
    assert prepared.lines[0].indices.dtype == np.uint32
    assert prepared.lines[0].indices.flags.c_contiguous


def test_prepare_scene_lifts_line2_to_z_zero() -> None:
    prepared = prepare_scene(
        Scene("line2").add(Line2((1.0, 2.0), (3.0, 4.0))),
        tolerance=1e-3,
    )

    np.testing.assert_allclose(
        prepared.lines[0].vertices,
        [[1.0, 2.0, 0.0], [3.0, 4.0, 0.0]],
    )


def test_prepare_scene_uses_open_and_closed_curve_indices() -> None:
    open_curve = Polyline3(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 1.0), (1.0, 1.0, 1.0))
    )
    closed_curve = Polyline3(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 1.0), (1.0, 1.0, 1.0)),
        closed=True,
    )

    open_line = prepare_scene(Scene("open").add(open_curve)).lines[0]
    closed_line = prepare_scene(Scene("closed").add(closed_curve)).lines[0]

    np.testing.assert_array_equal(open_line.indices, [[0, 1], [1, 2]])
    np.testing.assert_array_equal(closed_line.indices, [[0, 1], [1, 2], [2, 0]])
    assert not np.array_equal(closed_line.vertices[0], closed_line.vertices[-1])


@pytest.mark.parametrize(
    ("curve", "expected"),
    [
        (
            Line2((0.0, 0.0), (1.0, 2.0)),
            [[3.0, 4.0, 5.0], [4.0, 6.0, 5.0]],
        ),
        (
            Line3((0.0, 0.0, 1.0), (1.0, 2.0, 3.0)),
            [[3.0, 4.0, 6.0], [4.0, 6.0, 8.0]],
        ),
    ],
    ids=["2d", "3d"],
)
def test_prepare_scene_applies_curve_pose_once(
    curve: object,
    expected: list[list[float]],
) -> None:
    prepared = prepare_scene(
        Scene("posed").add(curve, pose=(3.0, 4.0, 5.0)),
        tolerance=1e-3,
    )

    np.testing.assert_allclose(prepared.lines[0].vertices, expected)


def test_prepare_scene_samples_curves_at_requested_tolerance_without_mutation() -> None:
    circle = Circle2((0.0, 0.0), 1.0)
    scene = Scene("circle").add(circle)

    coarse = prepare_scene(scene, tolerance=0.5)
    fine = prepare_scene(scene, tolerance=1e-3)

    assert len(fine.lines[0].vertices) > len(coarse.lines[0].vertices)
    assert scene.objects[0].target is circle


@pytest.mark.parametrize("tolerance", [0.0, -1.0, float("inf"), float("nan")])
def test_prepare_scene_rejects_invalid_tolerance_for_raw_lines(tolerance: float) -> None:
    scene = Scene("line").add(((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)))

    with pytest.raises(ViewError, match="tolerance"):
        prepare_scene(scene, tolerance=tolerance)


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
