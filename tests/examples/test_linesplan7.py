from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from cady import Mesh3

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_DIR = ROOT / "examples" / "linesplan7"


def test_boundary_extension_mesh_divides_projected_strip_before_lofting() -> None:
    module = _load_linesplan7_main()

    mesh = module.boundary_extension_mesh(
        ((0.0, 3000.0, 0.0), (10.0, 3000.0, 0.0)),
        node_spacing=1000.0,
    )

    assert len(mesh.faces) == 3
    assert all(len(face) == 4 for face in mesh.faces)
    assert _y_values_at_x(mesh, 0.0) == pytest.approx(
        [3000.0, 2000.0, 1000.0, 0.0]
    )
    assert _y_values_at_x(mesh, 10.0) == pytest.approx(
        [3000.0, 2000.0, 1000.0, 0.0]
    )


def test_boundary_extension_mesh_does_not_subdivide_short_projection_columns() -> None:
    module = _load_linesplan7_main()

    mesh = module.boundary_extension_mesh(
        ((0.0, 20_000.0, 0.0), (10.0, 1500.0, 0.0)),
        node_spacing=1000.0,
    )

    assert _y_values_at_x(mesh, 0.0) == pytest.approx(
        [20_000.0, *range(19_000, 0, -1000), 0.0]
    )
    assert _y_values_at_x(mesh, 10.0) == pytest.approx([1500.0, 0.0])


def test_boundary_extension_mesh_subdivides_non_short_projection_columns() -> None:
    module = _load_linesplan7_main()

    mesh = module.boundary_extension_mesh(
        ((0.0, 20_000.0, 0.0), (10.0, 2500.0, 0.0)),
        node_spacing=1000.0,
    )

    assert _y_values_at_x(mesh, 10.0) == pytest.approx(
        [2500.0, 1666.6666667, 833.3333333, 0.0]
    )


def test_boundary_extension_mesh_welds_projection_rows_already_on_centerline() -> None:
    module = _load_linesplan7_main()

    mesh = module.boundary_extension_mesh(
        ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0)),
        node_spacing=1000.0,
    )

    assert mesh.vertices == ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0))
    assert mesh.faces == ()
    assert mesh.edges == ((0, 1),)


def test_pizza_triangulate_mesh_uses_reduced_inner_polygon_without_parameters() -> None:
    module = _load_linesplan7_pizza_triangulate()

    polygon = module.polygon_mesh_from_points(
        (
            (0.0, 0.0, 0.0),
            (1.0, 1.8, 0.0),
            (2.4, 3.0, 0.0),
            (4.0, 3.4, 0.0),
            (5.8, 3.3, 0.0),
            (7.2, 2.5, 0.0),
            (8.0, 1.2, 0.0),
            (8.2, 0.0, 0.0),
            (5.9, 0.0, 0.0),
            (3.7, 0.0, 0.0),
            (1.6, 0.0, 0.0),
        )
    )

    triangulated = module.pizza_triangulate_mesh(polygon)
    outer_count = len(polygon.vertices)
    added_count = len(triangulated.vertices) - outer_count
    first_inner_ring_count = module._inner_polygon_vertex_count(outer_count)

    assert all(len(face) == 3 for face in triangulated.faces)
    assert added_count >= first_inner_ring_count + 1
    assert len(triangulated.faces) > outer_count
    assert module._mesh_min_angle_degrees(triangulated) >= module.PIZZA_MIN_ANGLE_DEGREES


def test_pizza_triangulate_skips_ring_when_center_fill_meets_min_angle() -> None:
    module = _load_linesplan7_pizza_triangulate()

    polygon = module.polygon_mesh_from_points(
        (
            (1.0, 0.0, 0.0),
            (0.5, 0.8660254, 0.0),
            (-0.5, 0.8660254, 0.0),
            (-1.0, 0.0, 0.0),
            (-0.5, -0.8660254, 0.0),
            (0.5, -0.8660254, 0.0),
        )
    )

    triangulated = module.pizza_triangulate_mesh(polygon)

    assert len(triangulated.vertices) == len(polygon.vertices) + 1
    assert len(triangulated.faces) == len(polygon.vertices)
    assert module._mesh_min_angle_degrees(triangulated) >= module.PIZZA_MIN_ANGLE_DEGREES


def test_pizza_triangulate_splits_polygon_after_ring_attempts_miss_angle() -> None:
    module = _load_linesplan7_pizza_triangulate()

    polygon = module.polygon_mesh_from_points(
        (
            (0.0, 0.0, 0.0),
            (0.2, 0.5, 0.0),
            (1.5, 1.0, 0.0),
            (4.0, 1.2, 0.0),
            (8.0, 1.2, 0.0),
            (11.0, 1.0, 0.0),
            (12.5, 0.5, 0.0),
            (13.0, 0.0, 0.0),
            (10.0, 0.0, 0.0),
            (7.0, 0.0, 0.0),
            (4.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
        )
    )

    triangulated = module.pizza_triangulate_mesh(polygon)
    outer_count = len(polygon.vertices)
    split = module._best_chord_split(
        module.np.asarray(polygon.vertices, dtype=module.np.float64),
        list(range(outer_count)),
    )
    assert split is not None
    start, end = split
    expected_midpoint = tuple(
        (polygon.vertices[start][axis] + polygon.vertices[end][axis]) * 0.5
        for axis in range(3)
    )

    assert all(len(face) == 3 for face in triangulated.faces)
    assert triangulated.vertices[outer_count] == pytest.approx(expected_midpoint)


def test_pizza_triangulate_examples_are_runnable() -> None:
    module = _load_linesplan7_pizza_triangulate()

    examples = module.example_meshes()
    summary = module.example_summary(examples)

    assert "target min angle 15 deg" in summary
    assert len(examples) >= 2
    assert all(
        all(len(face) == 3 for face in triangulated.faces)
        for _, _, triangulated in examples
    )


def test_snap_close_nodes_merges_close_vertices_and_deduplicates_edges() -> None:
    module = _load_linesplan7_snap_close_nodes()

    mesh = Mesh3(
        (
            (0.0, 0.0, 0.0),
            (0.0004, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
        ),
        ((0, 2, 3), (1, 2, 3)),
        ((0, 2), (1, 2), (2, 1), (0, 3), (1, 3), (2, 3)),
    )

    snapped = module.snap_close_nodes(mesh, tolerance=1e-3)

    assert snapped.vertices == (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    )
    assert snapped.faces == ((0, 1, 2),)
    assert snapped.edges == ((0, 1), (0, 2), (1, 2))


def test_snap_close_nodes_keeps_vertices_outside_tolerance() -> None:
    module = _load_linesplan7_snap_close_nodes()

    mesh = Mesh3(
        ((0.0, 0.0, 0.0), (0.0011, 0.0, 0.0), (1.0, 0.0, 0.0)),
        (),
        ((0, 1), (1, 2)),
    )

    snapped = module.snap_close_nodes(mesh, tolerance=1e-3)

    assert snapped == mesh


def test_snap_close_nodes_rejects_non_positive_tolerance() -> None:
    module = _load_linesplan7_snap_close_nodes()

    with pytest.raises(ValueError, match="tolerance"):
        module.snap_close_nodes(Mesh3((), ()), tolerance=0.0)


def _load_linesplan7_main() -> ModuleType:
    path = EXAMPLE_DIR / "main.py"
    return _load_module(path, "linesplan7_main_test")


def _load_linesplan7_pizza_triangulate() -> ModuleType:
    path = EXAMPLE_DIR / "pizza_triangulate.py"
    return _load_module(path, "linesplan7_pizza_triangulate_test")


def _load_linesplan7_snap_close_nodes() -> ModuleType:
    path = EXAMPLE_DIR / "snap_close_nodes.py"
    return _load_module(path, "linesplan7_snap_close_nodes_test")


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    add_to_path = str(EXAMPLE_DIR) not in sys.path
    if add_to_path:
        sys.path.insert(0, str(EXAMPLE_DIR))
    try:
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        if add_to_path:
            sys.path.remove(str(EXAMPLE_DIR))
    return module


def _y_values_at_x(mesh: object, x: float) -> list[float]:
    return [point[1] for point in mesh.vertices if point[0] == x]
