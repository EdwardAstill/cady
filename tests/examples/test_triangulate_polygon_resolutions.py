from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from cady import Mesh3
from cady.view import prepare_scene

ROOT = Path(__file__).resolve().parents[2]


def test_triangulate_resolutions_refines_same_polyline() -> None:
    module = _load_example_script()

    cases = module.triangulate_resolutions(
        module.example_polyline(),
        max_edge_lengths=(None, "auto", 0.75, 0.35, 0.18),
        tolerance=1e-6,
    )

    meshes = [mesh for _max_edge_length, mesh in cases]
    vertex_counts = [len(mesh.vertices) for mesh in meshes]
    face_counts = [len(mesh.faces) for mesh in meshes]

    assert all(isinstance(mesh, Mesh3) for mesh in meshes)
    assert vertex_counts == sorted(vertex_counts)
    assert face_counts == sorted(face_counts)
    assert vertex_counts[0] < vertex_counts[-1]
    assert face_counts[0] < face_counts[-1]
    assert [(len(mesh.vertices), len(mesh.faces)) for mesh in meshes] == [
        (11, 9),
        (12, 11),
        (37, 54),
        (146, 259),
        (517, 975),
    ]


def test_build_scene_places_resolution_meshes_next_to_each_other() -> None:
    module = _load_example_script()
    cases = module.triangulate_resolutions(
        module.example_polyline(),
        max_edge_lengths=(None, "auto", 0.75, 0.35),
        tolerance=1e-6,
    )

    scene = module.build_scene(cases)
    prepared = prepare_scene(scene, tolerance=1e-6)

    assert [item.object_name for item in scene.objects] == [
        "original boundary",
        "auto guide",
        "max edge 0.75",
        "max edge 0.35",
    ]
    assert [mesh.name for mesh in prepared.meshes] == [
        "original boundary",
        "auto guide",
        "max edge 0.75",
        "max edge 0.35",
    ]
    assert all(mesh.render_mode == "shaded" for mesh in prepared.meshes)
    assert prepared.meshes[0].vertices[:, 0].max() < prepared.meshes[1].vertices[:, 0].min()
    assert prepared.meshes[1].vertices[:, 0].max() < prepared.meshes[2].vertices[:, 0].min()
    assert prepared.meshes[2].vertices[:, 0].max() < prepared.meshes[3].vertices[:, 0].min()


def test_build_heuristic_scene_triangulates_from_polygon_mesh() -> None:
    module = _load_example_script()
    polygon = module.polygon_mesh_from_polyline(module.example_polyline(), tolerance=1e-6)

    scene = module.build_heuristic_scene(polygon, tolerance=1e-6)
    prepared = prepare_scene(scene, tolerance=1e-6)

    assert [item.object_name for item in scene.objects] == [
        "heuristic triangles",
        "input polygon",
    ]
    assert [mesh.name for mesh in prepared.meshes] == [
        "heuristic triangles",
        "input polygon",
    ]
    assert len(polygon.faces) == 1
    assert len(polygon.faces[0]) == len(polygon.vertices)
    assert prepared.meshes[0].vertices.shape[0] > len(polygon.vertices)
    assert prepared.meshes[0].faces.shape[0] > 1
    assert prepared.meshes[1].render_mode == "wireframe"
    assert prepared.meshes[1].faces.shape == (0, 3)
    assert prepared.meshes[1].edges.shape[0] == len(polygon.vertices)


def test_example_uses_local_triangulation_code() -> None:
    source = (ROOT / "examples" / "scripts" / "triangulate_polygon_resolutions.py").read_text()

    assert "cady.operations" not in source
    assert ".triangulate(" not in source
    assert "class TriangulationGuide" in source
    assert "def triangulate_curve3" in source


def _load_example_script() -> ModuleType:
    path = ROOT / "examples" / "scripts" / "triangulate_polygon_resolutions.py"
    spec = importlib.util.spec_from_file_location("triangulate_polygon_resolutions", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
