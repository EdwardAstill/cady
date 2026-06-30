from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import cady.view
from cady import Mesh2, Mesh3, Wireframe3
from cady.view import prepare_scene

ROOT = Path(__file__).resolve().parents[2]


def test_triangulate_closed_polyline_returns_mesh2() -> None:
    module = _load_example_script()

    polyline = module.example_polyline()
    mesh = module.triangulate_closed_polyline(polyline, tolerance=1e-6)

    assert isinstance(mesh, Mesh2)
    assert len(mesh.vertices) == 5
    assert len(mesh.edges) == 5
    assert len(mesh.faces) == 3
    assert mesh.area == 1.45


def test_build_scene_visualises_triangles_and_boundary() -> None:
    module = _load_example_script()

    polyline = module.example_polyline()
    mesh = module.triangulate_closed_polyline(polyline, tolerance=1e-6)
    scene = module.build_scene(polyline, mesh)
    prepared = prepare_scene(scene, tolerance=1e-6)

    assert [item.object_name for item in scene.objects] == [
        "triangulation",
        "closed_polyline",
    ]
    assert isinstance(scene.objects[0].target, Mesh3)
    assert isinstance(scene.objects[1].target, Wireframe3)
    assert [mesh.name for mesh in prepared.meshes] == [
        "triangulation",
        "closed_polyline",
    ]
    assert prepared.meshes[0].render_mode == "shaded"
    assert len(prepared.meshes[0].faces) == 3
    assert len(prepared.meshes[0].edges) == 7
    assert prepared.meshes[1].render_mode == "wireframe"
    assert len(prepared.meshes[1].edges) == 5


def test_main_prints_summary_and_opens_viewer(
    monkeypatch,
    capsys,
) -> None:
    module = _load_example_script()
    opened: list[tuple[object, float, str | None]] = []

    def fake_view_scene(
        scene: object,
        *,
        tolerance: float = 1e-3,
        title: str | None = None,
    ) -> None:
        opened.append((scene, tolerance, title))

    monkeypatch.setattr(cady.view, "view_scene", fake_view_scene)

    module.main()

    stdout = capsys.readouterr().out
    assert "cady closed Polyline2 triangulation demo" in stdout
    assert "mesh: 5 vertices, 5 boundary edges, 3 faces, area=1.45" in stdout
    assert len(opened) == 1
    assert opened[0][1:] == (module.TOLERANCE, "closed Polyline2 triangulation")


def _load_example_script() -> ModuleType:
    path = ROOT / "examples" / "scripts" / "triangulate_polyline2.py"
    spec = importlib.util.spec_from_file_location("triangulate_polyline2", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
