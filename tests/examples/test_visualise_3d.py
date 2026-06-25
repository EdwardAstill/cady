from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest


def test_visualise_3d_prints_scene_summary_without_opening_viewer(
    import_env: dict[str, str],
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "examples/scripts/visualise_3d.py",
            "--shape",
            "box",
            "--no-view",
        ],
        cwd=Path(__file__).resolve().parents[2],
        env=import_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout
    assert "cady 3D scene demo" in completed.stdout
    assert "Plain box" in completed.stdout
    assert "mesh:" in completed.stdout
    assert "VisPy viewer skipped." in completed.stdout


def test_visualise_linesplan_prints_summary_before_opening_viewer(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    opened_scenes: list[tuple[object, str | None]] = []
    module = _load_linesplan_script("visualise_linesplan_9m")
    visualisation = pytest.importorskip("cady.visualisation")

    def fake_view_scene(
        scene: object,
        *,
        tolerance: float = 1e-3,
        title: str | None = None,
    ) -> None:
        opened_scenes.append((scene, title))

    monkeypatch.setattr(module, "view_scene", fake_view_scene)
    monkeypatch.setattr(visualisation, "view_scene", fake_view_scene)
    module.main()

    stdout = capsys.readouterr().out
    assert "loaded 105 wireframes and 0 meshes" in stdout
    assert "scene objects: 105" in stdout
    assert "active camera: profile" in stdout
    assert "camera target: (0.0, 0.0, 0.0)" in stdout
    assert "camera scale: 152661" in stdout
    assert "wireframe vertices: 9715" in stdout
    assert "wireframe edges: 9610" in stdout
    assert [title for _scene, title in opened_scenes] == [
        "linesplan 9m - DXF wires",
        "linesplan 9m - Wireframe3D",
    ]
    wf_scene = opened_scenes[1][0]
    assert len(wf_scene.objects) == 1
    assert wf_scene.objects[0].object_name == "Wireframe3D"


def test_mirror_mesh_script_prints_mirrored_summary(
    import_env: dict[str, str],
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "examples/linesplan/mirror-mesh.py",
            "--no-view",
        ],
        cwd=Path(__file__).resolve().parents[2],
        env=import_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout
    assert "cady mirror wireframe demo" in completed.stdout
    assert "plane normal: (0, 1, 0)" in completed.stdout
    assert "source: 9715 vertices, 9610 edges, bounds=(0, -7.276e-12" in completed.stdout
    assert "mirrored: 9715 vertices, 9610 edges, bounds=(0, -19300" in completed.stdout
    assert "VisPy viewer skipped." in completed.stdout


def _load_linesplan_script(name: str) -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "examples" / "linesplan" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_example_script(name: str) -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "examples" / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
