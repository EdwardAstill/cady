from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from cady import Vec3, Wireframe3D
from cady.visualisation import prepare_scene


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


def test_visualise_mesh_boundary_prints_boundary_summary(
    import_env: dict[str, str],
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "examples/scripts/visualise_mesh_boundary.py",
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
    assert "cady mesh boundary demo" in completed.stdout
    assert "mesh: 825 vertices, 2089 edges, 1332 faces" in completed.stdout
    assert "boundary loops: 4 (112 edges, 26 edges, 22 edges, 22 edges)" in completed.stdout
    assert "VisPy viewer skipped." in completed.stdout


def test_visualise_mesh_boundary_scene_overlays_boundary_loops() -> None:
    module = _load_example_script("visualise_mesh_boundary")

    mesh = module.build_complicated_mesh()
    loops = mesh.boundary_loops
    boundaries = module._wireframes_from_boundary_loops(loops)
    scene = module.build_scene(mesh, boundaries)
    prepared = prepare_scene(scene, tolerance=1e-3)

    assert [obj.object_name for obj in scene.objects] == [
        "mesh",
        "boundary_loop_1",
        "boundary_loop_2",
        "boundary_loop_3",
        "boundary_loop_4",
    ]
    assert len(loops) == 4
    assert [len(loop.vertices) - 1 for loop in loops] == [112, 26, 22, 22]
    assert prepared.meshes[0].name == "mesh"
    assert len(prepared.meshes[0].edges) == 2089
    assert [mesh.name for mesh in prepared.meshes[1:]] == [
        "boundary_loop_1",
        "boundary_loop_2",
        "boundary_loop_3",
        "boundary_loop_4",
    ]
    assert all(mesh.render_mode == "wireframe" for mesh in prepared.meshes[1:])


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


def test_linesplan_wireframe_script_prints_wireframe_summary(
    import_env: dict[str, str],
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "examples/linesplan/wireframe.py",
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
    assert "cady wireframe demo" in completed.stdout
    assert "wireframe: 9715 vertices, 9610 edges" in completed.stdout
    assert "VisPy viewer skipped." in completed.stdout


def test_linesplan_mesh_boundary_script_uses_wireframe_to_mesh(
    import_env: dict[str, str],
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "examples/linesplan/mesh-boundary.py",
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
    assert "cady mesh boundary demo" in completed.stdout
    assert "source wireframe: 9715 vertices, 9610 edges" in completed.stdout
    assert (
        "mesh: 5915 vertices, 11674 edges, 11520 faces, "
        "bounds=(0, -19300, 0)"
    ) in completed.stdout
    assert "boundary loops: 1 (308 edges)" in completed.stdout
    assert "VisPy viewer skipped." in completed.stdout


def test_linesplan_wireframe_scene_draws_only_wireframe() -> None:
    module = _load_linesplan_script("wireframe")
    wireframe = Wireframe3D(
        (
            Vec3(0.0, 0.0, 0.0),
            Vec3(1.0, 0.0, 0.0),
            Vec3(1.0, 1.0, 0.0),
        ),
        ((0, 1), (1, 2)),
    )

    scene = module.build_scene(wireframe)
    prepared = prepare_scene(scene, tolerance=1e-3)

    assert [obj.object_name for obj in scene.objects] == ["wireframe"]
    assert isinstance(scene.objects[0].target, Wireframe3D)
    assert scene.objects[0].target is wireframe
    assert scene.objects[0].style == module.WIRE_STYLE
    assert len(prepared.meshes) == 1
    assert prepared.meshes[0].name == "wireframe"
    assert prepared.meshes[0].render_mode == "wireframe"
    assert len(prepared.meshes[0].edges) == 2
    assert len(prepared.meshes[0].faces) == 0


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
