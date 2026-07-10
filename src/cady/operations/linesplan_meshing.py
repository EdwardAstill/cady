"""Linesplan curve classification and station-network meshing helpers."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TypeAlias, cast

if TYPE_CHECKING:
    from cady.geometry.mesh import Mesh3
    from cady.geometry.wireframe import Wireframe3

Point3: TypeAlias = Sequence[float]


class _SourceCurveLike(Protocol):
    vertices: Iterable[Point3]
    layer: str | None
    source_index: int
    entity_type: str


@dataclass(frozen=True, slots=True)
class LinesplanCurve:
    """Normalised source curve record used by linesplan operations."""

    vertices: tuple[Point3, ...]
    layer: str | None = None
    source_index: int = 0
    entity_type: str = "POLYLINE"

    def __init__(
        self,
        vertices: Iterable[Point3],
        *,
        layer: str | None = None,
        source_index: int = 0,
        entity_type: str = "POLYLINE",
    ) -> None:
        object.__setattr__(self, "vertices", tuple(vertices))
        object.__setattr__(self, "layer", layer)
        object.__setattr__(self, "source_index", int(source_index))
        object.__setattr__(self, "entity_type", entity_type)


@dataclass(frozen=True, slots=True)
class RejectedLinesplanCurve:
    """Source curve that could not be classified into the network."""

    curve: LinesplanCurve
    reason: str


@dataclass(frozen=True, slots=True)
class GuideCoverage:
    """Coverage of one guide curve across ordered section stations."""

    guide_kind: str
    curve: LinesplanCurve
    matched_sections: tuple[int, ...]
    missing_sections: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class CompatibilityReport:
    """Summary of whether a classified linesplan can be meshed reliably."""

    section_count: int
    buttock_count: int
    waterline_count: int
    knuckle_count: int
    guide_coverages: tuple[GuideCoverage, ...]
    issues: tuple[str, ...]

    @property
    def is_compatible(self) -> bool:
        return not self.issues


@dataclass(frozen=True, slots=True)
class LinesplanNetwork:
    """Grouped linesplan curves and the report derived from them."""

    sections: tuple[LinesplanCurve, ...]
    buttocks: tuple[LinesplanCurve, ...]
    waterlines: tuple[LinesplanCurve, ...]
    knuckles: tuple[LinesplanCurve, ...]
    rejected: tuple[RejectedLinesplanCurve, ...]
    compatibility_report: CompatibilityReport


def classify_linesplan_curves(
    curves: Iterable[object] | Wireframe3,
    *,
    tolerance: float,
) -> LinesplanNetwork:
    """Group source curves into sections, buttocks, waterlines, and knuckles."""
    if tolerance <= 0:
        raise ValueError("tolerance must be positive")

    source_curves = _source_curves(curves)
    sections: list[LinesplanCurve] = []
    buttocks: list[LinesplanCurve] = []
    waterlines: list[LinesplanCurve] = []
    knuckles: list[LinesplanCurve] = []
    rejected: list[RejectedLinesplanCurve] = []

    for curve in source_curves:
        if len(curve.vertices) < 2:
            rejected.append(RejectedLinesplanCurve(curve, "curve has fewer than two vertices"))
            continue
        kind, reason = _classify_curve(curve, tolerance)
        if kind == "section":
            sections.append(curve)
        elif kind == "buttock":
            buttocks.append(curve)
        elif kind == "waterline":
            waterlines.append(curve)
        elif kind == "knuckle":
            knuckles.append(curve)
        else:
            rejected.append(RejectedLinesplanCurve(curve, reason))

    sections_tuple = tuple(sorted(sections, key=_station_x))
    buttocks_tuple = tuple(buttocks)
    waterlines_tuple = tuple(waterlines)
    knuckles_tuple = tuple(knuckles)
    return LinesplanNetwork(
        sections_tuple,
        buttocks_tuple,
        waterlines_tuple,
        knuckles_tuple,
        tuple(rejected),
        _compatibility_report(
            sections_tuple,
            buttocks_tuple,
            waterlines_tuple,
            knuckles_tuple,
            tolerance,
        ),
    )


def mesh_linesplan_network(
    network: LinesplanNetwork,
    *,
    tolerance: float,
    samples_per_curve: int = 12,
) -> Mesh3:
    """Build a simple quad-strip mesh across classified section curves."""
    from cady.geometry.mesh import Mesh3

    if tolerance <= 0:
        raise ValueError("tolerance must be positive")
    if samples_per_curve < 2:
        raise ValueError("samples_per_curve must be at least 2")

    sections = _merged_sections(network.sections, tolerance)
    if len(sections) < 2:
        raise ValueError("linesplan network requires at least two section curves")

    sample_values = _sample_values(sections, network, samples_per_curve, tolerance)
    rows = [[_point_on_section(section, value) for value in sample_values] for section in sections]

    vertices = tuple(point for row in rows for point in row)
    width = len(sample_values)
    faces: list[tuple[int, int, int]] = []
    for row in range(len(rows) - 1):
        for col in range(width - 1):
            a = row * width + col
            b = (row + 1) * width + col
            c = (row + 1) * width + col + 1
            d = row * width + col + 1
            faces.extend(((a, b, c), (a, c, d)))

    edge_set: set[tuple[int, int]] = set()
    for row in range(len(rows)):
        for col in range(width - 1):
            start = row * width + col
            edge_set.add((start, start + 1))
    for row in range(len(rows) - 1):
        for col in range(width):
            start = row * width + col
            edge_set.add((start, start + width))
    return Mesh3(vertices, tuple(faces), tuple(sorted(edge_set)))


def _source_curves(curves: Iterable[object] | Wireframe3) -> tuple[LinesplanCurve, ...]:
    from cady.geometry.wireframe import Wireframe3

    if isinstance(curves, Wireframe3):
        return tuple(
            LinesplanCurve((curves.vertices[vertex] for vertex in path), source_index=index)
            for index, path in enumerate(_wireframe_paths(curves))
        )
    result: list[LinesplanCurve] = []
    for index, curve in enumerate(curves):
        source = cast(_SourceCurveLike, curve)
        result.append(
            LinesplanCurve(
                source.vertices,
                layer=getattr(source, "layer", None),
                source_index=getattr(source, "source_index", index),
                entity_type=getattr(source, "entity_type", "POLYLINE"),
            )
        )
    return tuple(result)


def _wireframe_paths(wireframe: Wireframe3) -> tuple[tuple[int, ...], ...]:
    adjacency: dict[int, list[int]] = {}
    for start, end in wireframe.edges:
        adjacency.setdefault(start, []).append(end)
        adjacency.setdefault(end, []).append(start)

    visited_edges: set[tuple[int, int]] = set()
    paths: list[tuple[int, ...]] = []
    starts = sorted(adjacency, key=lambda vertex: (len(adjacency[vertex]) != 1, vertex))
    for start in starts:
        for neighbour in sorted(adjacency[start]):
            edge = (min(start, neighbour), max(start, neighbour))
            if edge in visited_edges:
                continue
            path = [start, neighbour]
            visited_edges.add(edge)
            previous, current = start, neighbour
            while True:
                # Continue only through unambiguous degree-2 runs; branching stays split.
                candidates = [
                    vertex
                    for vertex in sorted(adjacency[current])
                    if vertex != previous
                    and (min(current, vertex), max(current, vertex)) not in visited_edges
                ]
                if len(candidates) != 1:
                    break
                next_vertex = candidates[0]
                visited_edges.add((min(current, next_vertex), max(current, next_vertex)))
                path.append(next_vertex)
                previous, current = current, next_vertex
            paths.append(tuple(path))
    return tuple(paths)


def _classify_curve(curve: LinesplanCurve, tolerance: float) -> tuple[str | None, str]:
    layer = (curve.layer or "").strip().upper()
    if layer and layer != "0":
        if layer in {"SECTION", "SECTIONS", "STATION", "STATIONS"}:
            return "section", ""
        if layer in {"BUTTOCK", "BUTTOCKS"}:
            return "buttock", ""
        if layer in {"WATERLINE", "WATERLINES"}:
            return "waterline", ""
        if layer in {"KNUCKLE", "KNUCKLES"}:
            return "knuckle", ""
        return None, f"unrecognised linesplan layer {curve.layer!r}"

    constants = [
        ("section", _span([point[0] for point in curve.vertices]) <= tolerance),
        ("buttock", _span([point[1] for point in curve.vertices]) <= tolerance),
        ("waterline", _span([point[2] for point in curve.vertices]) <= tolerance),
    ]
    matches = [kind for kind, matched in constants if matched]
    if len(matches) == 1:
        return matches[0], ""
    return None, "fallback orientation is ambiguous"


def _compatibility_report(
    sections: tuple[LinesplanCurve, ...],
    buttocks: tuple[LinesplanCurve, ...],
    waterlines: tuple[LinesplanCurve, ...],
    knuckles: tuple[LinesplanCurve, ...],
    tolerance: float,
) -> CompatibilityReport:
    coverages: list[GuideCoverage] = []
    issues: list[str] = []
    for kind, guides in (
        ("buttock", buttocks),
        ("waterline", waterlines),
        ("knuckle", knuckles),
    ):
        for guide in guides:
            matched = tuple(
                index
                for index, section in enumerate(sections)
                if _guide_matches_section(guide, section, tolerance)
            )
            missing = tuple(index for index in range(len(sections)) if index not in matched)
            coverages.append(GuideCoverage(kind, guide, matched, missing))
            if missing:
                issues.append(
                    f"{kind} curve {guide.source_index} intersects "
                    f"{len(matched)}/{len(sections)} sections within tolerance"
                )
    return CompatibilityReport(
        len(sections),
        len(buttocks),
        len(waterlines),
        len(knuckles),
        tuple(coverages),
        tuple(issues),
    )


def _guide_matches_section(
    guide: LinesplanCurve,
    section: LinesplanCurve,
    tolerance: float,
) -> bool:
    station = _station_x(section)
    return any(abs(point[0] - station) <= tolerance for point in guide.vertices)


def _merged_sections(
    sections: tuple[LinesplanCurve, ...],
    tolerance: float,
) -> tuple[tuple[Point3, ...], ...]:
    by_station: dict[float, list[Point3]] = {}
    for section in sections:
        station = _station_x(section)
        key = next((value for value in by_station if abs(value - station) <= tolerance), station)
        by_station.setdefault(key, []).extend(section.vertices)

    merged: list[tuple[Point3, ...]] = []
    for _station, points in sorted(by_station.items()):
        useful = [
            point
            for point in points
            if _span([p[1] for p in points]) > tolerance or point[1] < 10.0
        ]
        deduped = _dedupe_points(useful, tolerance)
        merged.append(tuple(sorted(deduped, key=lambda point: (point[1], point[2], point[0]))))
    return tuple(section for section in merged if len(section) >= 2)


def _sample_values(
    sections: tuple[tuple[Point3, ...], ...],
    network: LinesplanNetwork,
    samples_per_curve: int,
    tolerance: float,
) -> tuple[float, ...]:
    max_y = min(max(point[1] for point in section) for section in sections)
    values = {max_y * index / (samples_per_curve - 1) for index in range(samples_per_curve)}
    for guide in network.buttocks + network.waterlines + network.knuckles:
        if _span([point[0] for point in guide.vertices]) > tolerance:
            for point in guide.vertices:
                if 0.0 <= point[1] <= max_y:
                    values.add(point[1])
    return tuple(sorted(values))


def _point_on_section(section: tuple[Point3, ...], y_value: float) -> Point3:
    for left, right in zip(section, section[1:], strict=False):
        if min(left[1], right[1]) <= y_value <= max(left[1], right[1]):
            span = right[1] - left[1]
            ratio = 0.0 if span == 0.0 else (y_value - left[1]) / span
            return (
                left[0] + (right[0] - left[0]) * ratio,
                y_value,
                left[2] + (right[2] - left[2]) * ratio,
            )
    nearest = min(section, key=lambda point: abs(point[1] - y_value))
    return (nearest[0], y_value, nearest[2])


def _dedupe_points(points: Iterable[Point3], tolerance: float) -> tuple[Point3, ...]:
    result: list[Point3] = []
    for point in points:
        if not any(
            abs(point[0] - other[0]) <= tolerance
            and abs(point[1] - other[1]) <= tolerance
            and abs(point[2] - other[2]) <= tolerance
            for other in result
        ):
            result.append(point)
    return tuple(result)


def _station_x(section: LinesplanCurve | tuple[Point3, ...]) -> float:
    vertices = section.vertices if isinstance(section, LinesplanCurve) else section
    return sum(point[0] for point in vertices) / len(vertices)


def _span(values: Iterable[float]) -> float:
    values_tuple = tuple(values)
    return max(values_tuple) - min(values_tuple)


__all__ = [
    "CompatibilityReport",
    "GuideCoverage",
    "LinesplanCurve",
    "LinesplanNetwork",
    "RejectedLinesplanCurve",
    "classify_linesplan_curves",
    "mesh_linesplan_network",
]
