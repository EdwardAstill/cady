from __future__ import annotations

import importlib.util
from math import isclose
from pathlib import Path
from types import ModuleType


def test_linesplan3_keel_order_walks_around_profile_without_diagonal() -> None:
    module = _load_linesplan3_module()

    centre_top, centre_bottom, outer_bottom, outer_top = module.build_keel()

    for ct, cb, ot, ob in zip(
        centre_top.points(),
        centre_bottom.points(),
        outer_top.points(),
        outer_bottom.points(),
        strict=True,
    ):
        assert isclose(ot[0], ct[0])
        assert isclose(ob[0], ct[0])
        assert ot[1] == module.KEEL_THICKNESS
        assert ob[1] == module.KEEL_THICKNESS
        assert isclose(ot[2], ct[2])
        assert isclose(cb[2], ct[2] - module.KEEL_DEPTH)
        assert isclose(ob[2], ct[2] - module.KEEL_DEPTH)


def test_linesplan3_ordered_keel_loft_uses_build_order_directly() -> None:
    linesplan = _load_linesplan3_module()
    loft = _load_linesplan3_loft_module()

    mesh = loft.loft_ordered_polylines(
        linesplan.build_keel(),
        station_count=3,
        close_profile=False,
    )

    assert len(mesh.vertices) == 12
    assert len(mesh.faces) == 12

    centre_top, centre_bottom, outer_bottom, outer_top = linesplan.build_keel()
    assert mesh.vertices[:4] == (
        centre_top.points()[0],
        centre_bottom.points()[0],
        outer_bottom.points()[0],
        outer_top.points()[0],
    )


def test_linesplan3_strip_loft_builds_adjacent_pair_meshes() -> None:
    from cady import Polyline3

    loft = _load_linesplan3_loft_module()

    first = Polyline3([(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)])
    second = Polyline3([(0.0, 0.0, 1.0), (2.0, 0.0, 1.0)])
    third = Polyline3([(0.0, 1.0, 1.0), (2.0, 1.0, 1.0)])

    mesh = loft.loft_polyline_strips(
        [first, second, third],
        station_count=3,
    )

    assert len(mesh.vertices) == 12
    assert len(mesh.faces) == 8
    assert mesh.vertices[:2] == (first.points()[0], second.points()[0])
    assert mesh.vertices[6:8] == (second.points()[0], third.points()[0])


def test_linesplan3_strip_loft_keel_uses_build_order_as_strips() -> None:
    linesplan = _load_linesplan3_module()
    loft = _load_linesplan3_loft_module()

    centre_top, centre_bottom, outer_bottom, outer_top = linesplan.build_keel()

    mesh = loft.loft_polyline_strips(
        [centre_top, centre_bottom, outer_bottom, outer_top],
        station_count=3,
    )

    assert len(mesh.vertices) == 18
    assert len(mesh.faces) == 12
    assert mesh.vertices[:2] == (centre_top.points()[0], centre_bottom.points()[0])
    assert mesh.vertices[6:8] == (centre_bottom.points()[0], outer_bottom.points()[0])
    assert mesh.vertices[12:14] == (outer_bottom.points()[0], outer_top.points()[0])


def test_linesplan3_hull_and_keel_share_root_polyline_geometry() -> None:
    module = _load_linesplan3_module()

    hull_root = module.build_linespan()[0]
    keel_root = module.build_keel()[0]

    assert hull_root.points() == keel_root.points()


def _load_linesplan3_module() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "examples" / "linesplan3" / "linesplan.py"
    spec = importlib.util.spec_from_file_location("linesplan3_linesplan", path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_linesplan3_loft_module() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "examples" / "linesplan3" / "loft.py"
    spec = importlib.util.spec_from_file_location("linesplan3_loft", path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
