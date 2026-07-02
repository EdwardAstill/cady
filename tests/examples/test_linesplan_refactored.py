from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from cady import Mesh3, Polyline3

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_DIR = ROOT / "examples" / "linesplan-refactored"


def test_clean_mesh_uses_local_polygon_triangulation() -> None:
    module = _load_refactored_module("clean_mesh")
    mesh = Mesh3(
        (
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ),
        ((0, 1, 2, 3),),
    )

    cleaned = module.clean_mesh(mesh, tolerance=1e-6)

    assert cleaned.vertices[:4] == mesh.vertices
    assert all(len(face) == 3 for face in cleaned.faces)
    assert len(cleaned.faces) == 2


def test_clean_mesh_expects_coplanar_faces_to_be_merged_first() -> None:
    module = _load_refactored_module("clean_mesh")
    mesh = Mesh3(
        (
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ),
        ((0, 1, 2), (0, 2, 3)),
    )

    cleaned = module.clean_mesh(mesh, tolerance=1e-6)

    assert len(cleaned.vertices) == 4
    assert len(cleaned.faces) == 2


def test_top_face_mesh_extracts_highest_coplanar_face() -> None:
    module = _load_refactored_module("clean_mesh")
    mesh = Mesh3(
        (
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
            (2.0, 0.0, 1.0),
            (2.0, 1.0, 1.0),
            (0.0, 1.0, 1.0),
        ),
        (
            (0, 1, 2, 3),
            (4, 5, 6, 7),
        ),
    )

    top_face = module.top_face_mesh(mesh, tolerance=1e-6)
    cleaned_top_face = module.clean_mesh(top_face, tolerance=1e-6)

    assert top_face.vertices == mesh.vertices[4:]
    assert top_face.faces == ((0, 1, 2, 3),)
    assert top_face.edges == ((0, 1), (1, 2), (2, 3), (3, 0))
    assert all(len(face) == 3 for face in cleaned_top_face.faces)


def test_clean_mesh_splits_only_non_planar_quads_before_merge() -> None:
    module = _load_refactored_module("clean_mesh")
    mesh = Mesh3(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
            (2.0, 0.0, 0.0),
            (3.0, 0.0, 0.0),
            (3.0, 1.0, 0.1),
            (2.0, 1.0, 0.0),
        ),
        ((0, 1, 2, 3), (4, 5, 6, 7)),
    )

    result = module.triangulate_non_planar_quads(mesh, tolerance=1e-6)

    assert result.faces == ((0, 1, 2, 3), (4, 5, 6), (4, 6, 7))


def test_clean_mesh_uses_refactored_triangulation_helper() -> None:
    source = (EXAMPLE_DIR / "clean_mesh.py").read_text()

    assert "from triangulate_polygon import TriangulationGuide, loop_edges, triangulate3d" in source
    assert "triangulate3d(" in source
    assert ".triangulate(" not in source


def test_clean_mesh_passes_guide_and_min_angle_to_local_triangulation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_refactored_module("clean_mesh")
    mesh = Mesh3(
        (
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ),
        ((0, 1, 2, 3),),
    )
    captured: dict[str, object] = {}

    def triangulate3d_spy(
        polygon: Mesh3,
        *,
        tolerance: float,
        guide: object,
        min_angle_degrees: float | None,
    ) -> Mesh3:
        captured["guide"] = guide
        captured["min_angle_degrees"] = min_angle_degrees
        return Mesh3(polygon.vertices, ((0, 1, 2), (0, 2, 3)), polygon.edges)

    monkeypatch.setattr(module, "triangulate3d", triangulate3d_spy)

    module.clean_mesh(mesh, guide="auto", min_angle_degrees=12.5)

    assert captured["guide"] == "auto"
    assert captured["min_angle_degrees"] == 12.5


def test_refactored_linesplan_cleans_merged_coplanar_mesh() -> None:
    source = (EXAMPLE_DIR / "main.py").read_text()

    assert "quad_triangular_mesh = triangulate_non_planar_quads(final_mesh)" in source
    assert "merged_coplanar_mesh = merge_coplanar_faces(quad_triangular_mesh)" in source
    assert "top_face = top_face_mesh(merged_coplanar_mesh)" in source
    assert "MIN_TRIANGLE_ANGLE_DEGREES = 20.0" in source
    assert "cleaned_mesh = clean_mesh(" in source
    assert "cleaned_top_face = clean_mesh(" in source
    assert source.count("min_angle_degrees=MIN_TRIANGLE_ANGLE_DEGREES") == 2


def test_walkthrough_shows_combined_mesh_before_closed_mesh() -> None:
    source = (EXAMPLE_DIR / "visualise.py").read_text()

    assert "def view_combined_mesh(hull: LinesplanHull) -> None:" in source
    assert "view_combined_mesh(hull)\n    view_final_mesh(hull)" in source


def test_refactored_linesplan_raises_when_mesh_closure_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_refactored_module("close_hull")

    def fail_close_mesh(self: Mesh3, *, tolerance: float = 1e-3) -> Mesh3:
        raise ValueError("mesh closure failed")

    monkeypatch.setattr(Mesh3, "close_mesh", fail_close_mesh)

    with pytest.raises(ValueError, match="mesh closure failed"):
        module.close_linesplan_hull(())


def test_process_stations_orients_after_snapping_fragments_before_preparing_points() -> None:
    module = _load_refactored_module("process_stations")
    lower_fragment = Polyline3(
        (
            (0.0, 0.0, -2_000.0),
            (0.0, 1.0, 0.0),
        )
    )
    upper_fragment = Polyline3(
        (
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 2_000.0),
            (0.0, 0.0, 4_000.0),
        )
    )

    processed = module.process_stations((lower_fragment, upper_fragment))

    assert processed.prepared_lines[0].points() == (
        (0.0, 0.0, 4_000.0),
        (0.0, 0.0, 2_000.0),
        (0.0, 1.0, 0.0),
    )


def test_process_stations_keeps_bow_station_after_first_outboard_point() -> None:
    module = _load_refactored_module("process_stations")
    bow_station = Polyline3(
        (
            (0.0, 0.0, 8_000.0),
            (0.0, 100.0, 7_990.0),
            (0.0, 700.0, 6_500.0),
            (0.0, 500.0, 3_500.0),
            (0.0, 0.0, 1_000.0),
        )
    )

    processed = module.process_stations((bow_station,))

    assert processed.prepared_lines[0].points() == bow_station.points()


def test_refactored_linesplan_does_not_decimate_cleaned_mesh() -> None:
    source = (EXAMPLE_DIR / "main.py").read_text()

    assert ".decimate(" not in source
    assert "DECIMATED_TARGET_FACES" not in source


def _load_refactored_module(name: str) -> ModuleType:
    path = EXAMPLE_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"linesplan_refactored_{name}", path)
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
