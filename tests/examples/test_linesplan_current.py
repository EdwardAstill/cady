from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_DIR = ROOT / "examples" / "linesplan"
INPUT_DIR = ROOT / "examples" / "inputs"


def test_linesplan_example_scales_settings_for_small_dxf() -> None:
    module = _load_linesplan_module()

    build = module.build_linesplan_mesh(INPUT_DIR / "3d_lp.dxf")

    assert len(build.station_polylines) == 23
    assert len(build.prepared_station_polylines) == 23
    assert tuple(len(group) for group in build.polyline_groups) == (23, 0)
    assert build.settings.dxf_snap_tolerance < 1.0
    assert len(build.snapped_mesh.vertices) > 100
    assert len(build.snapped_mesh.faces) > 100


def test_linesplan_example_preserves_reference_dxf_settings() -> None:
    module = _load_linesplan_module()

    build = module.build_linesplan_mesh(INPUT_DIR / "linesplan_9m.dxf")

    assert tuple(len(group) for group in build.polyline_groups) == (65, 4)
    assert build.settings.dxf_snap_tolerance == 1000.0
    assert build.settings.node_spacing == 2000.0


def _load_linesplan_module() -> ModuleType:
    path = EXAMPLE_DIR / "main.py"
    spec = importlib.util.spec_from_file_location("linesplan_current_main", path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {path}")

    old_path = list(sys.path)
    local_modules = (
        "loft_polylines",
        "main",
        "pizza_triangulate",
        "process_polylines",
        "snap_close_nodes",
        "wireframe",
    )
    previous = {name: sys.modules.pop(name, None) for name in local_modules}
    try:
        sys.path.insert(0, str(EXAMPLE_DIR))
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path[:] = old_path
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
