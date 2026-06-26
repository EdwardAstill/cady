from __future__ import annotations

from dataclasses import dataclass

from cady.geometry import Wireframe3D
from cady.operations.linesplan import classify_linesplan_curves
from cady.vec import Vec3


@dataclass(frozen=True, slots=True)
class SourceCurve:
    vertices: tuple[tuple[float, float, float], ...]
    layer: str | None
    source_index: int
    entity_type: str = "POLYLINE"


def test_classify_linesplan_curves_uses_layer_metadata_first() -> None:
    curves = [
        SourceCurve(_section_vertices(0.0), "SECTIONS", 0),
        SourceCurve(_section_vertices(2.0), "SECTIONS", 1),
        SourceCurve(_section_vertices(4.0), "SECTIONS", 2),
        SourceCurve(((0.0, 1.0, 1.0), (2.0, 1.0, 1.0), (4.0, 1.0, 1.0)), "BUTTOCKS", 3),
        SourceCurve(((0.0, 2.0, 2.0), (2.0, 2.0, 2.0), (4.0, 2.0, 2.0)), "WATERLINES", 4),
        SourceCurve(((0.0, 0.0, 0.0), (2.0, 1.0, 1.0), (4.0, 2.0, 2.0)), "Knuckle", 5),
        SourceCurve(((99.0, 0.0, 0.0), (99.0, 1.0, 0.0)), "0", 6),
        SourceCurve(((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)), "GUIDES", 7),
        SourceCurve(((0.0, 0.0, 0.0),), "SECTIONS", 8),
    ]

    network = classify_linesplan_curves(curves, tolerance=1e-6)

    assert [curve.source_index for curve in network.sections] == [0, 1, 2]
    assert [curve.source_index for curve in network.buttocks] == [3]
    assert [curve.source_index for curve in network.waterlines] == [4]
    assert [curve.source_index for curve in network.knuckles] == [5]
    assert [rejected.curve.source_index for rejected in network.rejected] == [6, 7, 8]
    assert {rejected.reason for rejected in network.rejected} == {
        "fallback orientation is ambiguous",
        "unrecognised linesplan layer 'GUIDES'",
        "curve has fewer than two vertices",
    }

    report = network.compatibility_report
    assert report.is_compatible
    assert report.section_count == 3
    assert report.buttock_count == 1
    assert report.waterline_count == 1
    assert report.knuckle_count == 1
    guide_matches = [
        (coverage.guide_kind, coverage.matched_sections)
        for coverage in report.guide_coverages
    ]
    assert guide_matches == [
        ("buttock", (0, 1, 2)),
        ("waterline", (0, 1, 2)),
        ("knuckle", (0, 1, 2)),
    ]


def test_classify_linesplan_curves_falls_back_for_layer_zero_geometry() -> None:
    curves = [
        SourceCurve(((1.0, 0.0, 0.0), (1.0, 2.0, 2.0)), "0", 0),
        SourceCurve(((0.0, 3.0, 0.0), (2.0, 3.0, 2.0)), "0", 1),
        SourceCurve(((0.0, 0.0, 4.0), (2.0, 2.0, 4.0)), "0", 2),
    ]

    network = classify_linesplan_curves(curves, tolerance=1e-6)

    assert [curve.source_index for curve in network.sections] == [0]
    assert [curve.source_index for curve in network.buttocks] == [1]
    assert [curve.source_index for curve in network.waterlines] == [2]
    assert not network.rejected


def test_classify_linesplan_curves_falls_back_to_wireframe_orientation() -> None:
    vertices = (
        Vec3(0.0, 0.0, 0.0),
        Vec3(0.0, 1.0, 1.0),
        Vec3(0.0, 2.0, 2.0),
        Vec3(0.0, 3.0, 0.0),
        Vec3(1.0, 3.0, 1.0),
        Vec3(2.0, 3.0, 2.0),
        Vec3(0.0, 0.0, 7.0),
        Vec3(1.0, 1.0, 7.0),
        Vec3(2.0, 2.0, 7.0),
        Vec3(0.0, 5.0, 5.0),
        Vec3(1.0, 5.0, 5.0),
    )
    wireframe = Wireframe3D(
        vertices,
        (
            (0, 1),
            (1, 2),
            (3, 4),
            (4, 5),
            (6, 7),
            (7, 8),
            (9, 10),
        ),
    )

    network = classify_linesplan_curves(wireframe, tolerance=1e-6)

    assert len(network.sections) == 1
    assert len(network.buttocks) == 1
    assert len(network.waterlines) == 1
    assert len(network.rejected) == 1
    assert network.rejected[0].reason == "fallback orientation is ambiguous"


def test_compatibility_report_exposes_missing_guide_coverage() -> None:
    curves = [
        SourceCurve(_section_vertices(0.0), "SECTIONS", 0),
        SourceCurve(_section_vertices(2.0), "SECTIONS", 1),
        SourceCurve(((0.0, 1.0, 1.0), (0.0, 2.0, 2.0)), "BUTTOCKS", 2),
    ]

    network = classify_linesplan_curves(curves, tolerance=1e-6)

    assert not network.compatibility_report.is_compatible
    assert network.compatibility_report.guide_coverages[0].matched_sections == (0,)
    assert network.compatibility_report.guide_coverages[0].missing_sections == (1,)
    assert network.compatibility_report.issues == (
        "buttock curve 2 intersects 1/2 sections within tolerance",
    )


def _section_vertices(x: float) -> tuple[tuple[float, float, float], ...]:
    return ((x, 0.0, 0.0), (x, 1.0, 1.0), (x, 2.0, 2.0))
