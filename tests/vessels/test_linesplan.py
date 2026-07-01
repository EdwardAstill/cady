from __future__ import annotations

from pathlib import Path

from cady.geometry import Mesh3, Wireframe3
from cady.vessels import Linesplan

ROOT = Path(__file__).resolve().parents[2]
LINESPLAN_DXF = ROOT / "examples" / "inputs" / "linesplan_9m.dxf"


def test_linesplan_from_dxf_builds_cleaned_station_polylines() -> None:
    linesplan = Linesplan.from_dxf(LINESPLAN_DXF)

    assert len(linesplan.polylines) == 65
    assert all(len(polyline.points()) >= 2 for polyline in linesplan.polylines)
    assert all(
        point[1] == 0.0
        for polyline in linesplan.polylines
        for point in polyline.points()
        if abs(point[1]) <= 1e-3
    )


def test_linesplan_grid_wireframe_samples_station_grid() -> None:
    linesplan = Linesplan.from_dxf(LINESPLAN_DXF)

    wireframe = linesplan.to_grid_wireframe()

    assert isinstance(wireframe, Wireframe3)
    assert len(wireframe.vertices) == 65 * 48
    assert len(wireframe.edges) == 6192


def test_linesplan_to_mesh_returns_closed_triangular_mesh() -> None:
    linesplan = Linesplan.from_dxf(LINESPLAN_DXF)

    mesh = linesplan.to_mesh()

    assert isinstance(mesh, Mesh3)
    assert len(mesh.vertices) == 3674
    assert len(mesh.faces) == 7344
    assert all(len(face) == 3 for face in mesh.faces)
    face_edges = {
        tuple(sorted((start, end)))
        for face in mesh.faces
        for start, end in zip(face, (*face[1:], face[0]), strict=True)
    }
    mesh_edges = {tuple(sorted(edge)) for edge in mesh.edges}
    assert face_edges == mesh_edges
    assert mesh.boundary_loops == ()
    assert min(point[1] for point in mesh.vertices) == -max(point[1] for point in mesh.vertices)
