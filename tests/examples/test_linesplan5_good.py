from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from statistics import median
from types import ModuleType


def test_loft_polylines2_drops_tiny_station_sliver_before_mirroring() -> None:
    module = _load_linesplan5_good_script("loft_polylines2")

    station = _station_at_x(module.PROCESSED_STATION_POLYLINES, 11200.0)
    mirrored = _station_at_x(module.MIRRORED_STATION_POLYLINES, 11200.0)

    assert len(module.PROCESSED_STATION_POLYLINES) == 65
    assert not _contains_centreline_sliver(station.points())
    assert not _contains_centreline_sliver(mirrored.points())


def _station_at_x(polylines: object, x: float) -> object:
    matches = [
        polyline
        for polyline in polylines
        if median(point[0] for point in polyline.points()) == x
    ]
    assert len(matches) == 1
    return matches[0]


def _contains_centreline_sliver(points: object) -> bool:
    return any(abs(point[1]) < 1.0 and 2100.0 < point[2] < 2200.0 for point in points)


def _load_linesplan5_good_script(name: str) -> ModuleType:
    path = (
        Path(__file__).resolve().parents[2]
        / "examples"
        / "linesplan5-good"
        / f"{name}.py"
    )
    spec = importlib.util.spec_from_file_location(f"linesplan5_good_{name}", path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {path}")

    old_path = list(sys.path)
    old_wireframe = sys.modules.pop("wireframe", None)
    try:
        sys.path.insert(0, str(path.parent))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path[:] = old_path
        if old_wireframe is None:
            sys.modules.pop("wireframe", None)
        else:
            sys.modules["wireframe"] = old_wireframe
