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
        (33, 46),
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


def test_triangulate3d_accepts_polygon_mesh() -> None:
    module = _load_example_script()
    polygon = module.polygon_mesh_from_polyline(module.example_polyline(), tolerance=1e-6)

    original = module.triangulate3d(polygon, tolerance=1e-6)
    heuristic = module.triangulate3d(polygon, tolerance=1e-6, guide="auto")
    refined = module.triangulate3d(
        polygon,
        tolerance=1e-6,
        guide=module.TriangulationGuide(max_edge_length=0.75),
    )

    assert (len(original.vertices), len(original.faces)) == (11, 9)
    assert (len(heuristic.vertices), len(heuristic.faces)) == (33, 46)
    assert (len(refined.vertices), len(refined.faces)) == (37, 54)


def test_shape_cases_cover_difficult_polygons() -> None:
    module = _load_example_script()

    cases = module.triangulate_shape_cases(tolerance=1e-6)

    assert [name for name, _polygon, _mesh in cases] == [
        "coastal concave",
        "narrow channel",
        "comb teeth",
        "thin neck",
        "crescent moon",
        "long sliver",
        "tapered needle",
        "hairline slot",
        "jagged bay",
    ]
    assert [
        (name, len(polygon.vertices), len(mesh.vertices), len(mesh.faces))
        for name, polygon, mesh in cases
    ] == [
        ("coastal concave", 11, 33, 46),
        ("narrow channel", 8, 33, 39),
        ("comb teeth", 20, 56, 72),
        ("thin neck", 12, 32, 40),
        ("crescent moon", 13, 46, 69),
        ("long sliver", 4, 17, 20),
        ("tapered needle", 6, 93, 131),
        ("hairline slot", 8, 48, 55),
        ("jagged bay", 20, 67, 101),
    ]


def test_auto_api_resolves_comb_teeth() -> None:
    module = _load_example_script()

    mesh = module.triangulate3d(
        module.polygon_mesh_from_points(module.COMB_POINTS),
        tolerance=module.TOLERANCE,
        guide="auto",
    )

    assert len(mesh.vertices) > len(module.COMB_POINTS)
    assert len(mesh.faces) > len(module.COMB_POINTS) - 2


def test_build_shape_scene_prepares_shape_gallery() -> None:
    module = _load_example_script()
    cases = module.triangulate_shape_cases(tolerance=1e-6)

    scene = module.build_shape_scene(cases)
    prepared = prepare_scene(scene, tolerance=1e-6)

    assert len(scene.objects) == len(cases) * 2
    assert len(prepared.meshes) == len(cases) * 2
    assert prepared.meshes[0].name == "coastal concave heuristic triangles"
    assert prepared.meshes[1].name == "coastal concave input polygon"
    assert all(mesh.render_mode == "wireframe" for mesh in prepared.meshes[1::2])
    assert all(mesh.faces.shape == (0, 3) for mesh in prepared.meshes[1::2])


def test_min_angle_cases_compare_same_skinny_polygon() -> None:
    module = _load_example_script()

    cases = module.triangulate_min_angle_cases(tolerance=1e-6)

    assert [angle for angle, _polygon, _mesh in cases] == [None, 5.0, 10.0, 15.0]
    assert [
        (angle, len(polygon.vertices), len(mesh.vertices), len(mesh.faces))
        for angle, polygon, mesh in cases
    ] == [
        (None, 8, 48, 55),
        (5.0, 8, 53, 61),
        (10.0, 8, 149, 213),
        (15.0, 8, 280, 433),
    ]
    assert module._mesh_min_angle_degrees(cases[0][2]) < 10.0
    assert module._mesh_min_angle_degrees(cases[2][2]) >= 10.0
    assert module._mesh_min_angle_degrees(cases[3][2]) >= 15.0


def test_build_min_angle_scene_prepares_skinny_comparison() -> None:
    module = _load_example_script()
    cases = module.triangulate_min_angle_cases(tolerance=1e-6)

    scene = module.build_min_angle_scene(cases)
    prepared = prepare_scene(scene, tolerance=1e-6)

    assert [item.object_name for item in scene.objects] == [
        "auto guide triangles",
        "auto guide input polygon",
        "min angle 5 triangles",
        "min angle 5 input polygon",
        "min angle 10 triangles",
        "min angle 10 input polygon",
        "min angle 15 triangles",
        "min angle 15 input polygon",
    ]
    assert len(prepared.meshes) == len(scene.objects)
    assert all(mesh.render_mode == "wireframe" for mesh in prepared.meshes[1::2])
    assert all(mesh.faces.shape == (0, 3) for mesh in prepared.meshes[1::2])


def test_example_uses_triangulation_api() -> None:
    source = (ROOT / "examples" / "scripts" / "triangulate_polygon_resolutions.py").read_text()

    assert "from cady.operations import TriangulationGuide" in source
    assert ".triangulate(" in source
    assert "min_angle_degrees=min_angle_degrees" in source
    assert ": object" not in source
    assert "class TriangulationGuide" not in source
    assert "def triangulate_mesh3" not in source
    assert "def triangulate3d(" in source


def _load_example_script() -> ModuleType:
    path = ROOT / "examples" / "scripts" / "triangulate_polygon_resolutions.py"
    spec = importlib.util.spec_from_file_location("triangulate_polygon_resolutions", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
