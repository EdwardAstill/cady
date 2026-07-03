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


def _load_linesplan7_main() -> ModuleType:
    path = EXAMPLE_DIR / "main.py"
    spec = importlib.util.spec_from_file_location("linesplan7_main_test", path)
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
