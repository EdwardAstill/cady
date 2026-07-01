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


def test_mesh_decimate_prints_summary_without_opening_viewer(
    import_env: dict[str, str],
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "examples/scripts/mesh_decimate.py",
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
    assert "views: surface, closed-box, closed-cylinder, linesplan-dxf" in completed.stdout
    assert "open height-field mesh" in completed.stdout
    assert "source: 247 vertices, 678 edges, 432 faces, closed=no" in completed.stdout
    assert "decimated: 77 vertices, 196 edges, 120 faces, closed=no" in completed.stdout
    assert "target faces: 120" in completed.stdout
    assert "removed faces: 312" in completed.stdout
    assert "closed box mesh" in completed.stdout
    assert "source: 8 vertices, 18 edges, 12 faces, closed=yes" in completed.stdout
    assert "decimated: 7 vertices, 15 edges, 10 faces, closed=yes" in completed.stdout
    assert "closed cylinder mesh" in completed.stdout
    assert "source: 26 vertices, 72 edges, 48 faces, closed=yes" in completed.stdout
    assert "decimated: 10 vertices, 24 edges, 16 faces, closed=yes" in completed.stdout
    assert "closed linesplan mesh from DXF" in completed.stdout
    assert "source: 778 vertices, 2328 edges, 1552 faces, closed=yes" in completed.stdout
    assert "decimated: 152 vertices, 450 edges, 300 faces, closed=yes" in completed.stdout
    assert "VisPy viewer skipped." in completed.stdout


def test_mesh_decimate_scenes_draw_faces_and_all_face_edges() -> None:
    module = _load_example_script("mesh_decimate")

    results = tuple(
        module.decimate_case(case, tolerance=1e-9)
        for case in module.build_cases("all")
    )

    assert [result.key for result in results] == [
        "surface",
        "closed-box",
        "closed-cylinder",
        "linesplan-dxf",
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
        (12, 18, 10, 15, "yes"),
        (48, 72, 16, 24, "yes"),
        (1552, 2328, 300, 450, "yes"),
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
    assert "camera: orthographic" in stdout
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


def test_linesplan4_adds_all_polyline_intersection_nodes() -> None:
    module = _load_linesplan4_script("pc_from_dxf")

    result = module.dxf_intersection_pointcloud(
        module.LINESPLAN_DXF,
        tolerance=1e-3,
        intersection_tolerance=80.0,
        repeat_distance=90.0,
    )
    cloud = module.pointcloud_from_dxf(
        module.LINESPLAN_DXF,
        tolerance=1e-3,
        intersection_tolerance=80.0,
        repeat_distance=90.0,
    )
    scene = module.build_scene(result)

    assert not hasattr(result, "node_rows")
    assert isinstance(cloud, PointCloud3)
    assert cloud == result.cloud
    assert result.curve_count == 105
    assert result.intersecting_pair_count == 2036
    assert result.raw_intersection_count == 2503
    assert len(result.cloud.vertices) == 2381
    assert any(
        abs(point[0] - 181447.46) <= 90.0 and abs(point[2] - 4999.91) <= 90.0
        for point in result.cloud.vertices
    )

    prepared = prepare_scene(scene, tolerance=1e-3)
    assert [mesh.name for mesh in prepared.meshes] == [
        "source_wireframe",
        "intersection_nodes",
    ]
    assert prepared.meshes[1].render_mode == "points"
    assert len(prepared.meshes[1].vertices) == 2381


def test_linesplan4_mesh_from_dxf_pointcloud() -> None:
    module = _load_linesplan4_script("mesh_from_pc")

    result = module.mesh_from_dxf_pointcloud(
        module.LINESPLAN_DXF,
        tolerance=1e-3,
        intersection_tolerance=80.0,
        repeat_distance=90.0,
    )
    scene = module.build_scene(result)

    assert isinstance(result.cloud, PointCloud3)
    assert isinstance(result.mesh, Mesh3)
    assert len(result.cloud.vertices) == 2381
    assert len(result.mesh.vertices) == 587
    assert len(result.mesh.edges) == 4985
    assert len(result.mesh.faces) == 3085

    prepared = prepare_scene(scene, tolerance=1e-3)
    assert [mesh.name for mesh in prepared.meshes] == [
        "source_wireframe",
        "mesh_from_point_cloud",
        "intersection_nodes",
    ]
    assert prepared.meshes[0].render_mode == "wireframe"
    assert prepared.meshes[1].render_mode == "shaded"
    assert prepared.meshes[2].render_mode == "points"


def test_linesplan5_curve_network_mesh_overlays_intersection_nodes() -> None:
    module = _load_linesplan5_script("curve_network_mesh")

    result = module.curve_network_mesh_from_dxf(
        module.LINESPLAN_DXF,
        tolerance=1e-3,
        intersection_tolerance=80.0,
        repeat_distance=90.0,
    )
    scene = module.build_scene(result)

    assert isinstance(result.cloud, PointCloud3)
    assert isinstance(result.intersection_wireframe, Wireframe3)
    assert isinstance(result.mesh, Mesh3)
    assert len(result.cloud.vertices) == 2381
    assert len(result.node_result.intersections) == 2503
    assert result.mesh.vertices == result.cloud.vertices
    assert module.mesh_uses_only_intersection_nodes(result)
    assert len(result.network.sections) == 72
    assert len(result.network.buttocks) == 20
    assert len(result.network.waterlines) == 9
    assert len(result.network.knuckles) == 4
    assert len(result.intersection_wireframe.vertices) == 2381
    assert len(result.intersection_wireframe.edges) == 4397
    assert len(result.mesh.vertices) == 2381
    assert len(result.mesh.edges) == 4397
    assert len(result.mesh.faces) == 1434
    assert all(len(face) == 4 for face in result.mesh.faces)
    assert len(result.mesh.triangulated_faces(tolerance=1e-3)) == 2868

    curve_edges = set(result.intersection_wireframe.edges)
    face_edges = {
        (min(start, end), max(start, end))
        for face in result.mesh.faces
        for start, end in zip(face, face[1:] + face[:1], strict=True)
    }
    assert face_edges <= curve_edges

    prepared = prepare_scene(scene, tolerance=1e-3)
    assert [mesh.name for mesh in prepared.meshes] == [
        "intersection_patch_mesh",
        "intersection_node_wireframe",
        "intersection_nodes",
    ]
    assert prepared.meshes[0].faces.shape == (2868, 3)
    assert prepared.meshes[0].render_mode == "shaded"
    assert prepared.meshes[1].render_mode == "wireframe"
    assert prepared.meshes[2].render_mode == "points"


def test_linesplan5_ball_pivoting_mesh_uses_intersection_nodes_without_source_edges() -> None:
    module = _load_linesplan5_script("ball_pivoting")

    result = module.ball_pivoting_mesh_from_dxf(
        module.LINESPLAN_DXF,
        tolerance=1e-3,
        intersection_tolerance=80.0,
        repeat_distance=90.0,
        ball_radius=900.0,
        neighbour_count=18,
    )
    scene = module.build_scene(result)

    assert isinstance(result.cloud, PointCloud3)
    assert isinstance(result.mesh, Mesh3)
    assert result.mesh.vertices == result.cloud.vertices
    assert len(result.cloud.vertices) == 2381
    assert len(result.mesh.vertices) == 2381
    assert len(result.mesh.edges) == 2318
    assert len(result.mesh.faces) == 1267
    assert all(len(face) == 3 for face in result.mesh.faces)

    face_edges = {
        (min(start, end), max(start, end))
        for face in result.mesh.faces
        for start, end in zip(face, face[1:] + face[:1], strict=True)
    }
    assert set(result.mesh.edges) == face_edges

    prepared = prepare_scene(scene, tolerance=1e-3)
    assert [mesh.name for mesh in prepared.meshes] == [
        "ball_pivoting_mesh",
        "intersection_nodes",
    ]
    assert prepared.meshes[0].render_mode == "shaded"
    assert prepared.meshes[1].render_mode == "points"


def test_linesplan5_pc_from_dxf_exports_plain_points_by_default() -> None:
    module = _load_linesplan5_script("pc_from_dxf")

    points = module.points_from_dxf(module.LINESPLAN_DXF)
    result = module.dxf_intersection_pointcloud(module.LINESPLAN_DXF)

    assert isinstance(points, tuple)
    assert all(isinstance(point, tuple) for point in points)
    assert points == result.cloud.vertices
    assert len(points) == 2124
    assert result.repeat_distance == 900.0


def _load_linesplan_script(name: str) -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "examples" / "linesplan" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_linesplan4_script(name: str) -> ModuleType:
    return _load_linesplan_dir_script("linesplan4", name)


def _load_linesplan5_script(name: str) -> ModuleType:
    return _load_linesplan_dir_script("linesplan5", name)


def _load_linesplan_dir_script(directory: str, name: str) -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "examples" / directory / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    script_dir = str(path.parent)
    add_to_path = script_dir not in sys.path
    if add_to_path:
        sys.path.insert(0, script_dir)
    previous_pc_from_dxf = sys.modules.pop("pc_from_dxf", None)
    try:
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        if previous_pc_from_dxf is not None:
            sys.modules["pc_from_dxf"] = previous_pc_from_dxf
        if add_to_path:
            sys.path.remove(script_dir)
    return module


def _load_example_script(name: str) -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "examples" / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
