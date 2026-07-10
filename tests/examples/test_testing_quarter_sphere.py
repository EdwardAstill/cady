from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from math import isclose
from pathlib import Path
from types import ModuleType

from cady.geometry import Point3
from cady.view import prepare_scene

ROOT = Path(__file__).resolve().parents[2]
TESTING_DIR = ROOT / "examples" / "testing"


def test_slice_y_values_are_generated_from_min_max_and_count() -> None:
    module = _load_testing_example()

    y_values = module.slice_y_values(
        min_y=module.MIN_SLICE_Y,
        max_y=module.MAX_SLICE_Y,
        slices=module.SLICES,
    )
    steps = [right - left for left, right in zip(y_values[:-1], y_values[1:], strict=True)]

    assert len(y_values) == module.SLICES
    assert y_values[0] == module.MIN_SLICE_Y
    assert y_values[-1] == module.MAX_SLICE_Y
    assert all(isclose(step, steps[0]) for step in steps)


def test_slice_y_values_require_more_than_two_slices() -> None:
    module = _load_testing_example()

    try:
        module.slice_y_values(min_y=-5.0, max_y=5.0, slices=2)
    except ValueError as exc:
        assert "greater than 2" in str(exc)
    else:
        raise AssertionError("slice_y_values should reject slices <= 2")


def test_quarter_sphere_arc_angles_are_ordered_from_one_side_through_middle() -> None:
    module = _load_testing_example()

    assert isinstance(module.ARC_ANGLES, list)
    assert [module.pi / 2.0, module.pi / 4.0, 0.0] == module.ARC_ANGLES


def test_quarter_sphere_slice_planes_add_intersection_nodes() -> None:
    module = _load_testing_example()
    polylines = module.quarter_sphere_polylines(
        radius=module.RADIUS,
        samples=module.SAMPLES,
    )
    wireframe = module.wireframe_from_polylines(polylines.values())
    y_values = module.slice_y_values(
        min_y=module.MIN_SLICE_Y,
        max_y=module.MAX_SLICE_Y,
        slices=module.SLICES,
    )
    nodes = module.intersection_nodes(wireframe, y_values=y_values)
    node_cloud = module.intersection_nodes_to_point_cloud(nodes)

    assert len(nodes) == len(wireframe.edges)
    assert all(isinstance(edge_nodes, list) for edge_nodes in nodes)
    assert len(node_cloud.vertices) == 2 + len(module.ARC_ANGLES) * (module.SLICES - 2)
    assert Counter(round(vertex[1], 6) for vertex in node_cloud.vertices) == Counter({
        round(y, 6): 1 if index in (0, len(y_values) - 1) else len(module.ARC_ANGLES)
        for index, y in enumerate(y_values)
    })


def test_quarter_sphere_scene_displays_intersection_mesh_and_nodes() -> None:
    module = _load_testing_example()
    polylines = module.quarter_sphere_polylines(
        radius=module.RADIUS,
        samples=module.SAMPLES,
    )
    wireframe = module.wireframe_from_polylines(polylines.values())
    y_values = module.slice_y_values(
        min_y=module.MIN_SLICE_Y,
        max_y=module.MAX_SLICE_Y,
        slices=module.SLICES,
    )
    planes = module.slice_planes(radius=module.RADIUS, y_values=y_values)
    nodes = module.intersection_nodes(wireframe, y_values=y_values)

    scene = module.build_scene(wireframe, planes, nodes)
    prepared = prepare_scene(scene, tolerance=1e-3)
    node_mesh = module.intersection_nodes_to_edge_mesh(nodes)
    expected_mesh_vertices = len(module.ARC_ANGLES) * module.SLICES
    expected_mesh_faces = (len(module.ARC_ANGLES) - 1) * (module.SLICES - 1) * 2
    expected_mesh_edges = (
        len(module.ARC_ANGLES) * (module.SLICES - 1)
        + (len(module.ARC_ANGLES) - 1) * module.SLICES
    )
    expected_node_vertices = 2 + len(module.ARC_ANGLES) * (module.SLICES - 2)

    assert scene.objects[-2].object_name == "plane_intersection_mesh"
    assert scene.objects[-2].style == module.NODE_MESH_STYLE
    assert scene.objects[-2].target == node_mesh
    assert len(node_mesh.vertices) == expected_mesh_vertices
    assert len(node_mesh.faces) == expected_mesh_faces
    assert len(node_mesh.edges) == expected_mesh_edges
    assert scene.objects[-1].object_name == "plane_intersection_nodes"
    assert scene.objects[-1].style == module.NODE_STYLE
    assert scene.objects[-1].target == module.intersection_nodes_to_point_cloud(nodes)
    assert prepared.meshes[-2].name == "plane_intersection_mesh"
    assert prepared.meshes[-2].render_mode == "shaded"
    assert len(prepared.meshes[-2].vertices) == expected_mesh_vertices
    assert len(prepared.meshes[-2].faces) == expected_mesh_faces
    assert len(prepared.meshes[-2].edges) == expected_mesh_edges
    assert prepared.meshes[-1].name == "plane_intersection_nodes"
    assert prepared.meshes[-1].render_mode == "points"
    assert prepared.meshes[-1].point_size == module.NODE_STYLE.point_size
    assert len(prepared.meshes[-1].vertices) == expected_node_vertices


def test_intersection_nodes_to_edge_mesh_connects_matrix_neighbours() -> None:
    module = _load_testing_example()
    node_groups = [
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
        ],
        [
            (0.0, 1.0, 0.0),
            (1.0, 1.0, 0.0),
            (2.0, 1.0, 0.0),
        ],
    ]

    mesh = module.intersection_nodes_to_edge_mesh(node_groups)

    assert mesh.vertices == (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (2.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (1.0, 1.0, 0.0),
        (2.0, 1.0, 0.0),
    )
    assert mesh.faces == (
        (0, 3, 1),
        (1, 3, 4),
        (1, 4, 2),
        (2, 4, 5),
    )
    assert mesh.edges == (
        (0, 1),
        (0, 3),
        (1, 2),
        (1, 4),
        (2, 5),
        (3, 4),
        (4, 5),
    )


def test_repair_examples_accept_semantic_polyline_vertices() -> None:
    for filename in ("testing2.py", "testing3.py", "testing4-bad.py"):
        module = _load_testing_script(filename)

        linesplan = module.quarter_sphere_linesplan(
            radius=module.RADIUS,
            samples=module.SAMPLES,
        )
        y_values = module.slice_y_values(
            min_y=module.MIN_SLICE_Y,
            max_y=module.MAX_SLICE_Y,
            slices=module.SLICES,
        )
        wireframe = module.wireframe_from_polylines(linesplan)
        wireframe_array = module.split_wireframe_with_planes(
            linesplan,
            y_values=y_values,
        )
        node_mesh = wireframe_array.to_mesh()

        assert isinstance(linesplan[0].vertices[0], Point3)
        assert len(wireframe.vertices) == 95
        assert len(wireframe.edges) == 96
        assert len(wireframe_array.node_array) == 3
        assert all(len(row) == 8 for row in wireframe_array.node_array)
        assert len(node_mesh.vertices) > 0


def test_strip_mesh_example_uses_shared_semantic_wireframe() -> None:
    module = _load_testing_script("testing5-strip-mesh.py")

    y_values = module.slice_y_values(
        min_y=module.MIN_SLICE_Y,
        max_y=module.MAX_SLICE_Y,
        slices=module.SLICES,
    )
    strip_mesh = module.build_distance_refined_strip_mesh(
        module.WIREFRAME_OBJECT.linesplan,
        y_values=y_values,
        max_segment_length=module.MAX_SEGMENT_LENGTH,
        refinement_rows=module.REFINEMENT_ROWS,
    )

    assert isinstance(module.WIREFRAME_OBJECT.linesplan[0].vertices[0], Point3)
    assert len(module.WIREFRAME_OBJECT.wireframe.vertices) == 95
    assert len(strip_mesh.base_node_array) == 3
    assert all(len(row) == 8 for row in strip_mesh.base_node_array)
    assert len(strip_mesh.mesh.vertices) == 20
    assert len(strip_mesh.mesh.faces) == 24


def _load_testing_example() -> ModuleType:
    return _load_testing_script("testing.py", "quarter_sphere_testing")


def _load_testing_script(filename: str, name: str | None = None) -> ModuleType:
    path = TESTING_DIR / filename
    module_name = name or Path(filename).stem.replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    script_dir = str(path.parent)
    add_to_path = script_dir not in sys.path
    if add_to_path:
        sys.path.insert(0, script_dir)
    previous_wireframe = None
    had_wireframe = False
    if module_name != "wireframe":
        had_wireframe = "wireframe" in sys.modules
        previous_wireframe = sys.modules.pop("wireframe", None)
    try:
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        if module_name != "wireframe":
            if had_wireframe:
                sys.modules["wireframe"] = previous_wireframe
            else:
                sys.modules.pop("wireframe", None)
        if add_to_path:
            sys.path.remove(script_dir)
