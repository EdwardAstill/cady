from __future__ import annotations

import pytest

from cady import Assembly, Body3D, DisplayStyle, Mesh3D, Part, Vec3, box


def test_mesh_view_builds_centred_wire_scene_and_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    visualisation = pytest.importorskip("cady.visualisation")
    opened: list[tuple[object, float, str | None]] = []
    mesh = Mesh3D(
        (Vec3(10.0, 0.0, 0.0), Vec3(12.0, 0.0, 0.0)),
        (),
        ((0, 1),),
    )

    def fake_view_scene(
        scene: object,
        *,
        tolerance: float = 1e-3,
        title: str | None = None,
    ) -> None:
        opened.append((scene, tolerance, title))

    monkeypatch.setattr(visualisation, "view_scene", fake_view_scene)

    result = mesh.view(title="wire", tolerance=0.25)

    assert result is None
    assert len(opened) == 1
    scene, tolerance, title = opened[0]
    assert tolerance == 0.25
    assert title == "wire"
    assert len(scene.objects) == 1
    assert scene.objects[0].target is mesh
    assert scene.objects[0].pose is not None
    assert scene.objects[0].style.render_mode == "wireframe"
    assert scene.cameras[0][1].projection == "orthographic"


def test_body_view_accepts_scene_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    visualisation = pytest.importorskip("cady.visualisation")
    opened: list[object] = []
    body = Body3D.box(width=1.0, depth=0.5, height=0.25)
    style = DisplayStyle(color=(0.2, 0.4, 0.8), render_mode="shaded")

    def fake_view_scene(
        scene: object,
        *,
        tolerance: float = 1e-3,
        title: str | None = None,
    ) -> None:
        opened.append(scene)

    monkeypatch.setattr(visualisation, "view_scene", fake_view_scene)

    body.view(name="body", style=style, projection="perspective", center=False)

    scene = opened[0]
    assert scene.objects[0].object_name == "body"
    assert scene.objects[0].pose is None
    assert scene.objects[0].style is style
    assert scene.cameras[0][1].projection == "perspective"


def test_part_and_assembly_have_view_methods(monkeypatch: pytest.MonkeyPatch) -> None:
    visualisation = pytest.importorskip("cady.visualisation")
    opened: list[object] = []
    part = Part("box").with_body(box(1.0, 1.0, 1.0))
    assembly = Assembly("assy").add(part)

    def fake_view_scene(
        scene: object,
        *,
        tolerance: float = 1e-3,
        title: str | None = None,
    ) -> None:
        opened.append(scene)

    monkeypatch.setattr(visualisation, "view_scene", fake_view_scene)

    part.view(title="part")
    assembly.view(title="assembly")

    assert [scene.name for scene in opened] == ["part", "assembly"]
