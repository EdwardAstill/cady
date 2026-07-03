from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

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
    inner_count = added_count - 1

    assert all(len(face) == 3 for face in triangulated.faces)
    assert 3 <= inner_count < outer_count
    assert len(triangulated.faces) > outer_count
    assert module._mesh_min_angle_degrees(triangulated) >= module.PIZZA_MIN_ANGLE_DEGREES


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


def _load_linesplan7_main() -> ModuleType:
    path = EXAMPLE_DIR / "main.py"
    return _load_module(path, "linesplan7_main_test")


def _load_linesplan7_pizza_triangulate() -> ModuleType:
    path = EXAMPLE_DIR / "pizza_triangulate.py"
    return _load_module(path, "linesplan7_pizza_triangulate_test")


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
