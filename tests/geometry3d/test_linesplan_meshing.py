from __future__ import annotations

import pytest

from cady.geometry import Mesh3D
from cady.operations.linesplan import (
    LinesplanCurve,
    classify_linesplan_curves,
    mesh_linesplan_network,
)


def test_mesh_linesplan_network_builds_section_loft_without_source_overlay_edges() -> None:
    network = classify_linesplan_curves(
        (
            LinesplanCurve(_section_vertices(0.0), layer="SECTIONS", source_index=0),
            LinesplanCurve(_section_vertices(2.0), layer="SECTIONS", source_index=1),
            LinesplanCurve(_section_vertices(4.0), layer="SECTIONS", source_index=2),
            LinesplanCurve(
                ((99.0, 0.0, 0.0), (99.0, 1.0, 0.0)),
                layer="0",
                source_index=3,
            ),
        ),
        tolerance=1e-6,
    )

    mesh = mesh_linesplan_network(network, tolerance=1e-6, samples_per_curve=3)

    assert isinstance(mesh, Mesh3D)
    assert len(mesh.vertices) == 9
    assert len(mesh.faces) == 8
    assert len(mesh.edges) == 12
    assert mesh.bounds()[1].x == 4.0
    face_edges = set()
    for a, b, c in mesh.faces:
        for start, end in ((a, b), (b, c), (c, a)):
            face_edges.add((min(start, end), max(start, end)))
    assert all((min(start, end), max(start, end)) in face_edges for start, end in mesh.edges)


def test_mesh_linesplan_network_adds_guide_derived_sample_columns() -> None:
    network = classify_linesplan_curves(
        (
            LinesplanCurve(
                ((0.0, 0.0, 0.0), (0.0, 2.0, 2.0)),
                layer="SECTIONS",
                source_index=0,
            ),
            LinesplanCurve(
                ((2.0, 0.0, 0.0), (2.0, 2.0, 2.0)),
                layer="SECTIONS",
                source_index=1,
            ),
            LinesplanCurve(
                ((0.0, 1.0, 1.0), (2.0, 1.0, 1.0)),
                layer="WATERLINES",
                source_index=2,
            ),
        ),
        tolerance=1e-6,
    )

    mesh = mesh_linesplan_network(network, tolerance=1e-6, samples_per_curve=2)

    assert len(mesh.vertices) == 6
    assert len(mesh.faces) == 4
    assert (0.0, 1.0, 1.0) in [vertex.tuple() for vertex in mesh.vertices]
    assert (2.0, 1.0, 1.0) in [vertex.tuple() for vertex in mesh.vertices]


def test_mesh_linesplan_network_merges_same_station_fragments() -> None:
    network = classify_linesplan_curves(
        (
            LinesplanCurve(_section_vertices(0.0), layer="SECTIONS", source_index=0),
            LinesplanCurve(
                ((1.0, 0.0, 0.0), (1.0, 1.0, 1.0)),
                layer="0",
                source_index=1,
            ),
            LinesplanCurve(
                ((1.0, 1.0, 1.0), (1.0, 2.0, 2.0)),
                layer="SECTIONS",
                source_index=2,
            ),
            LinesplanCurve(
                ((1.0, 1.0, 1.0), (1.0, 2.0, 2.0)),
                layer="SECTIONS",
                source_index=3,
            ),
            LinesplanCurve(
                ((1.0, 99.0, 99.0), (1.0, 99.0001, 99.0001)),
                layer="SECTIONS",
                source_index=4,
            ),
            LinesplanCurve(_section_vertices(2.0), layer="SECTIONS", source_index=5),
        ),
        tolerance=1e-6,
    )

    mesh = mesh_linesplan_network(network, tolerance=1e-6, samples_per_curve=3)

    assert len(mesh.vertices) == 9
    assert len(mesh.faces) == 8
    assert max(vertex.y for vertex in mesh.vertices) == 2.0
    assert max(vertex.z for vertex in mesh.vertices) == 2.0


def test_mesh_linesplan_network_rejects_network_without_two_sections() -> None:
    network = classify_linesplan_curves(
        (LinesplanCurve(_section_vertices(0.0), layer="SECTIONS", source_index=0),),
        tolerance=1e-6,
    )

    with pytest.raises(ValueError, match="at least two section curves"):
        mesh_linesplan_network(network, tolerance=1e-6)


def test_mesh_linesplan_network_rejects_too_few_samples() -> None:
    network = classify_linesplan_curves(
        (
            LinesplanCurve(_section_vertices(0.0), layer="SECTIONS", source_index=0),
            LinesplanCurve(_section_vertices(2.0), layer="SECTIONS", source_index=1),
        ),
        tolerance=1e-6,
    )

    with pytest.raises(ValueError, match="samples_per_curve"):
        mesh_linesplan_network(network, tolerance=1e-6, samples_per_curve=1)


def _section_vertices(x: float) -> tuple[tuple[float, float, float], ...]:
    return ((x, 0.0, 0.0), (x, 1.0, 1.0), (x, 2.0, 2.0))
