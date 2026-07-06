from __future__ import annotations

from pathlib import Path

import pytest

from cady.geometry import Mesh3, Wireframe3
from cady.vessels import Linesplan, LinesplanMeshSettings

ROOT = Path(__file__).resolve().parents[2]
LINESPLAN_DXF = ROOT / "examples" / "files" / "linesplan_9m.dxf"
SMALL_LINESPLAN_DXF = ROOT / "examples" / "files" / "3d_lp.dxf"


def test_linesplan_from_dxf_builds_cleaned_station_polylines() -> None:
    linesplan = Linesplan.from_dxf(LINESPLAN_DXF)

    assert len(linesplan.polylines) == 65
    assert tuple(len(group) for group in linesplan.polyline_groups) == (65, 4)
    assert isinstance(linesplan.settings, LinesplanMeshSettings)
    assert all(len(polyline.points()) >= 2 for polyline in linesplan.polylines)
    assert all(
        point[1] == 0.0
        for polyline in linesplan.polylines
        for point in polyline.points()
        if abs(point[1]) <= 1e-3
    )


def test_linesplan_to_wireframe_returns_cleaned_connected_station_lines() -> None:
    linesplan = Linesplan.from_dxf(LINESPLAN_DXF)

    wireframe = linesplan.to_wireframe()

    assert isinstance(wireframe, Wireframe3)
    assert len(wireframe.vertices) == 3283
    assert len(wireframe.edges) == 3218


def test_linesplan_grid_wireframe_samples_station_grid() -> None:
    linesplan = Linesplan.from_dxf(LINESPLAN_DXF)

    wireframe = linesplan.to_grid_wireframe()

    assert isinstance(wireframe, Wireframe3)
    assert len(wireframe.vertices) == 65 * 48
    assert len(wireframe.edges) == 6127


def test_linesplan_from_dxf_nodes_on_polyline_sets_default_sample_count() -> None:
    linesplan = Linesplan.from_dxf(LINESPLAN_DXF, nodes_on_polyline=12)

    wireframe = linesplan.to_grid_wireframe()

    assert linesplan.nodes_on_polyline == 12
    assert len(wireframe.vertices) == 65 * 12
    assert len(wireframe.edges) == 1483


def test_linesplan_grid_wireframe_accepts_legacy_nodes_per_station_override() -> None:
    linesplan = Linesplan.from_dxf(LINESPLAN_DXF, nodes_on_polyline=12)

    wireframe = linesplan.to_grid_wireframe(nodes_per_station=8)

    assert len(wireframe.vertices) == 65 * 8
    assert len(wireframe.edges) == 967


def test_linesplan_rejects_invalid_nodes_on_polyline() -> None:
    with pytest.raises(TypeError, match="nodes_on_polyline must be an integer"):
        Linesplan.from_dxf(LINESPLAN_DXF, nodes_on_polyline=12.5)

    with pytest.raises(ValueError, match="nodes_on_polyline must be at least 2"):
        Linesplan.from_dxf(LINESPLAN_DXF, nodes_on_polyline=1)


def test_linesplan_rejects_conflicting_sample_count_names() -> None:
    linesplan = Linesplan.from_dxf(LINESPLAN_DXF)

    with pytest.raises(ValueError, match="use either nodes_on_polyline or nodes_per_station"):
        linesplan.to_grid_wireframe(nodes_on_polyline=12, nodes_per_station=8)


def test_linesplan_to_mesh_rejects_conflicting_spacing_controls() -> None:
    linesplan = Linesplan.from_dxf(LINESPLAN_DXF)

    with pytest.raises(ValueError, match="use node_spacing or a node count"):
        linesplan.to_mesh(node_spacing=100.0, nodes_on_polyline=12)


def test_linesplan_to_mesh_returns_closed_triangular_mesh() -> None:
    linesplan = Linesplan.from_dxf(LINESPLAN_DXF)

    mesh = linesplan.to_mesh()

    assert isinstance(mesh, Mesh3)
    assert len(mesh.vertices) == 2962
    assert len(mesh.faces) == 5920
    assert len(mesh.edges) == 8880
    assert all(len(face) == 3 for face in mesh.faces)
    assert mesh.closed
    assert mesh.boundary_loops == ()
    assert min(point[1] for point in mesh.vertices) == -max(point[1] for point in mesh.vertices)


def test_linesplan_settings_scale_for_small_dxf() -> None:
    linesplan = Linesplan.from_dxf(SMALL_LINESPLAN_DXF)
    mesh = linesplan.to_mesh()

    assert len(linesplan.polylines) == 23
    assert tuple(len(group) for group in linesplan.polyline_groups) == (23, 0)
    assert linesplan.settings.dxf_snap_tolerance < 1.0
    assert len(mesh.vertices) == 1263
    assert len(mesh.faces) == 2522
    assert mesh.closed


def test_linesplan_api_does_not_import_from_playground() -> None:
    source = (ROOT / "src" / "cady" / "vessels" / "linesplan.py").read_text()

    assert "playground" not in source
