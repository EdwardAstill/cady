from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from cady import Mesh3, PointCloud3, Wireframe3
from cady.view import prepare_scene


def test_visualise_3_prints_scene_summary_without_opening_viewer(
    import_env: dict[str, str],
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "examples/scripts/visualise_3.py",
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
    assert [len(loop) - 1 for loop in loops] == [112, 26, 22, 22]
    assert prepared.meshes[0].name == "mesh"
    assert len(prepared.meshes[0].edges) == 2089
    assert [mesh.name for mesh in prepared.meshes[1:]] == [
        "boundary_loop_1",
        "boundary_loop_2",
        "boundary_loop_3",
        "boundary_loop_4",
    ]
    assert all(mesh.render_mode == "wireframe" for mesh in prepared.meshes[1:])


def test_pointcloud2mesh_prints_process_summary(import_env: dict[str, str]) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "examples/scripts/pointcloud2mesh.py",
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
    assert "cady point cloud meshing demo" in completed.stdout
    assert "advancing-front point array" in completed.stdout
    assert "points: 81" in completed.stdout
    assert "271 faces" in completed.stdout
    assert "VisPy viewer skipped." in completed.stdout


def test_pointcloud2mesh_scene_overlays_clouds_and_meshes() -> None:
    module = _load_example_script("pointcloud2mesh")

    cases = module.build_cases(grid_size=5)
    scene = module.build_scene(cases)
    prepared = prepare_scene(scene, tolerance=1e-3)

    assert [obj.object_name for obj in scene.objects] == [
        "advancing-front point array mesh",
        "advancing-front point array samples",
    ]
    assert isinstance(scene.objects[0].target, Mesh3)
    assert isinstance(scene.objects[1].target, PointCloud3)
    assert [mesh.render_mode for mesh in prepared.meshes] == [
        "shaded",
        "points",
    ]
    assert [len(mesh.vertices) for mesh in prepared.meshes] == [25, 25]
    assert [len(mesh.faces) for mesh in prepared.meshes] == [53, 0]


def test_pointcloud2mesh_samples_irregular_y_positions() -> None:
    module = _load_example_script("pointcloud2mesh")

    samples = module.surface_samples(7)
    first_column_y = [samples[row * 7].point[1] for row in range(7)]
    y_steps = [
        round(first_column_y[index + 1] - first_column_y[index], 6)
        for index in range(len(first_column_y) - 1)
    ]

    assert first_column_y[0] == -1.0
    assert first_column_y[-1] == 1.0
    assert first_column_y == sorted(first_column_y)
    assert len(set(y_steps)) > 1


def test_visualise_linesplan_prints_summary_before_opening_viewer(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    opened_scenes: list[tuple[object, str | None]] = []
    module = _load_linesplan_script("visualise_linesplan_9m")
    view = pytest.importorskip("cady.view")

    def fake_view_scene(
        scene: object,
        *,
        tolerance: float = 1e-3,
        title: str | None = None,
    ) -> None:
        opened_scenes.append((scene, title))

    monkeypatch.setattr(module, "view_scene", fake_view_scene)
    monkeypatch.setattr(view, "view_scene", fake_view_scene)
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
        "linesplan 9m - Wireframe3",
    ]
    wf_scene = opened_scenes[1][0]
    assert len(wf_scene.objects) == 1
    assert wf_scene.objects[0].object_name == "Wireframe3"


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
        "mesh: 5915 vertices, 17434 edges, 11520 faces, "
        "bounds=(0, -19300, 0)"
    ) in completed.stdout
    assert "boundary loops: 1 (308 edges)" in completed.stdout
    assert "VisPy viewer skipped." in completed.stdout


def test_linesplan_wireframe_scene_draws_only_wireframe() -> None:
    module = _load_linesplan_script("wireframe")
    wireframe = Wireframe3(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
        ),
        ((0, 1), (1, 2)),
    )

    scene = module.build_scene(wireframe)
    prepared = prepare_scene(scene, tolerance=1e-3)

    assert [obj.object_name for obj in scene.objects] == ["wireframe"]
    assert isinstance(scene.objects[0].target, Wireframe3)
    assert scene.objects[0].target is wireframe
    assert scene.objects[0].style == module.WIRE_STYLE
    assert len(prepared.meshes) == 1
    assert prepared.meshes[0].name == "wireframe"
    assert prepared.meshes[0].render_mode == "wireframe"
    assert len(prepared.meshes[0].edges) == 2
    assert len(prepared.meshes[0].faces) == 0


def test_linesplan4_marks_projected_front_crossing() -> None:
    module = _load_linesplan4_script("mesh_pc_dxf")

    curves = module.read_polyline_curves(module.LINESPLAN_DXF)
    result = module.mesh_point_cloud_from_intersections(
        curves,
        source=module.wireframe_from_curves(curves),
        tolerance=1e-3,
        intersection_tolerance=40.0,
        repeat_distance=50.0,
    )
    scene = module.build_scene(result)

    assert len(result.projected_misses) == 1
    miss = result.projected_misses[0]
    assert {miss.left_source_index, miss.right_source_index} == {5, 16}
    assert miss.gap > result.intersection_tolerance
    assert round(miss.projected_point[0]) == 181448
    assert round(miss.projected_point[2]) == 5000
    assert "projected_miss_1_ring" in [item.object_name for item in scene.objects]
    assert "projected_miss_curve_5" in [item.object_name for item in scene.objects]
    assert "projected_miss_curve_16" in [item.object_name for item in scene.objects]

    prepared = prepare_scene(scene, tolerance=1e-3)
    prepared_names = [mesh.name for mesh in prepared.meshes]
    assert "projected_miss_1_ring" in prepared_names
    assert "projected_miss_curve_5" in prepared_names
    assert "projected_miss_curve_16" in prepared_names


def _load_linesplan_script(name: str) -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "examples" / "linesplan" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_linesplan4_script(name: str) -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "examples" / "linesplan4" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
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
