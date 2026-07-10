from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

from cady import Mesh3, PointCloud3
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
            "examples/scripts/meshes/visualise_mesh_boundary.py",
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
            "examples/scripts/meshes/pointcloud2mesh.py",
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


def test_mesh_decimate_prints_summary_without_opening_viewer(
    import_env: dict[str, str],
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "examples/scripts/meshes/mesh_decimate.py",
            "--case",
            "surface",
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
    assert "cady mesh decimation demo" in completed.stdout
    assert "views: surface" in completed.stdout
    assert "open height-field mesh" in completed.stdout
    assert "source: 247 vertices, 678 edges, 432 faces, closed=no" in completed.stdout
    assert "decimated: 77 vertices, 196 edges, 120 faces, closed=no" in completed.stdout
    assert "target faces: 120" in completed.stdout
    assert "removed faces: 312" in completed.stdout
    assert "VisPy viewer skipped." in completed.stdout


def test_mesh_decimate_scenes_draw_faces_and_all_face_edges() -> None:
    module = _load_example_script("mesh_decimate")

    results = tuple(
        module.decimate_case(case, tolerance=1e-9)
        for case in module.build_cases("surface")
    )

    assert [result.key for result in results] == [
        "surface",
    ]
    assert [
        (
            len(result.source.faces),
            len(result.source.edges),
            len(result.decimated.faces),
            len(result.decimated.edges),
            module._closed_state(result.decimated),
        )
        for result in results
    ] == [
        (432, 678, 120, 196, "no"),
    ]

    for result in results:
        prepared = prepare_scene(module.build_result_scene(result), tolerance=1e-9)
        assert [mesh.name for mesh in prepared.meshes] == ["source_mesh", "decimated_mesh"]
        assert [mesh.render_mode for mesh in prepared.meshes] == ["shaded", "shaded"]
        assert all(len(mesh.faces) > 0 for mesh in prepared.meshes)
        assert all(len(mesh.edges) > 0 for mesh in prepared.meshes)


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


def _load_example_script(name: str) -> ModuleType:
    path = (
        Path(__file__).resolve().parents[2]
        / "examples"
        / "scripts"
        / "meshes"
        / f"{name}.py"
    )
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
