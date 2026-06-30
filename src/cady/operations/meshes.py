"""Mesh primitive and linesplan helpers plus meshing compatibility exports."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import acos, ceil, cos, pi, sin
from typing import TYPE_CHECKING, Protocol, TypeAlias, cast

from cady.operations.coordinates import add3, scale3
from cady.operations.lofting import LoftMesh, loft_section_polylines
from cady.operations.mesh_clipping import (
    KeepSide,
    close_boundary,
    close_planar_cap,
    close_to_plane,
    coerce_mesh,
    cut_mesh_by_plane,
)
from cady.operations.mesh_topology import (
    boundary_edges,
    boundary_edges_from_faces,
    compact_mesh_data,
    edge_loops,
    prune_dangling_edges,
    stitch_segments,
)
from cady.operations.meshing import (
    closed_polyline_mesh2,
    closed_polyline_mesh3,
    dedupe_closed,
    extrusion_mesh,
    mesh_from_triangles,
    region_loops_from_region,
    region_mesh,
    surface_region_mesh,
    triangulate_polygon,
    wireframe_mesh,
)
from cady.utils import positive, positive_tolerance

if TYPE_CHECKING:
    from cady.geometry.mesh import Mesh3
    from cady.geometry.plane3 import Plane3
    from cady.geometry.wireframe import Wireframe3

Face = tuple[int, int, int]
Edge = tuple[int, int]
Point2: TypeAlias = tuple[float, float]
Point3Tuple: TypeAlias = tuple[float, float, float]
Point3: TypeAlias = tuple[float, float, float]
Triangle3: TypeAlias = tuple[Point3Tuple, Point3Tuple, Point3Tuple]
Triangle2: TypeAlias = tuple[Point2, Point2, Point2]
FaceIndex = tuple[int, int, int]
EdgeIndex = tuple[int, int]


def segments_for_circle(radius: float, tolerance: float) -> int:
    """Estimate a polygon segment count that stays within a chord error."""
    tolerance = max(float(tolerance), 1e-9)
    if tolerance >= radius:
        return 12
    angle = 2.0 * acos(max(-1.0, min(1.0, 1.0 - tolerance / radius)))
    return max(12, ceil((2.0 * pi) / angle))


def prism_triangles(origin: Point3Tuple, size: Point3Tuple) -> list[Triangle3]:
    """Return triangles for an axis-aligned prism."""
    x0, y0, z0 = origin
    x1, y1, z1 = x0 + size[0], y0 + size[1], z0 + size[2]
    p = (
        (x0, y0, z0),
        (x1, y0, z0),
        (x1, y1, z0),
        (x0, y1, z0),
        (x0, y0, z1),
        (x1, y0, z1),
        (x1, y1, z1),
        (x0, y1, z1),
    )
    faces = (
        (0, 2, 1, 0, 3, 2),
        (4, 5, 6, 4, 6, 7),
        (0, 1, 5, 0, 5, 4),
        (1, 2, 6, 1, 6, 5),
        (2, 3, 7, 2, 7, 6),
        (3, 0, 4, 3, 4, 7),
    )
    return [(p[a], p[b], p[c]) for face in faces for a, b, c in (face[:3], face[3:])]


def basis_for_axis(
    axis: Point3Tuple,
    axis_name: str | None = None,
) -> tuple[Point3Tuple, Point3Tuple, Point3Tuple]:
    """Build a local orthonormal basis whose ``w`` axis follows ``axis``."""
    w = _normalised(axis)
    u = (1.0, 0.0, 0.0) if abs(w[2]) == 1 else _normalised(_cross((0.0, 0.0, 1.0), w))
    v = _normalised(_cross(w, u))
    if axis_name in {"+y", "-y"}:
        u, v = (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)
    elif axis_name in {"+x", "-x"}:
        u, v = (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
    return u, v, w


def extrusion_triangles(
    cap_triangles: list[Triangle2],
    loops: tuple[tuple[Point2, ...], ...],
    hole_flags: tuple[bool, ...],
    *,
    offset: Point3Tuple,
    axis: Point3Tuple,
    axis_name: str | None,
    distance: float,
) -> list[Triangle3]:
    """Extrude triangulated caps and region side walls along an axis."""
    u, v, w = basis_for_axis(axis, axis_name)
    start = offset
    end = _add(offset, _scale(w, distance))
    tris: list[Triangle3] = []
    for a, b, c in cap_triangles:
        tris.append((_map2(c, start, u, v), _map2(b, start, u, v), _map2(a, start, u, v)))
        tris.append((_map2(a, end, u, v), _map2(b, end, u, v), _map2(c, end, u, v)))
    for loop, is_hole in zip(loops, hole_flags, strict=True):
        pts = dedupe_closed(loop)
        for a, b in zip(pts, pts[1:] + pts[:1], strict=True):
            a0, b0 = _map2(a, start, u, v), _map2(b, start, u, v)
            a1, b1 = _map2(a, end, u, v), _map2(b, end, u, v)
            if is_hole:
                tris.append((a0, b1, b0))
                tris.append((a0, a1, b1))
            else:
                tris.append((a0, b0, b1))
                tris.append((a0, b1, a1))
    return tris


def revolution_triangles(
    profile_points: tuple[Point2, ...],
    *,
    axis_origin: Point3Tuple,
    axis_direction: Point3Tuple,
    angle_rad: float,
    tolerance: float,
) -> list[Triangle3]:
    """Approximate a surface of revolution around the positive Z axis."""
    pts2 = dedupe_closed(profile_points)
    axis = _normalised(axis_direction)
    if axis != (0.0, 0.0, 1.0):
        raise ValueError("Stage 1 revolution tessellation supports +Z axis")
    radius = max(abs(p[0] - axis_origin[0]) for p in pts2) or 1.0
    steps = max(12, ceil(abs(angle_rad) * radius / max(tolerance * 8, 1e-6)))
    steps = min(steps, 160)
    rings: list[list[Point3]] = []
    for i in range(steps):
        angle = angle_rad * i / steps
        ca, sa = cos(angle), sin(angle)
        rings.append([(p[0] * ca, p[0] * sa, p[1]) for p in pts2])
    tris: list[Triangle3] = []
    for i in range(steps):
        nxt = (i + 1) % steps
        for j in range(len(pts2)):
            a = rings[i][j]
            b = rings[i][(j + 1) % len(pts2)]
            c = rings[nxt][(j + 1) % len(pts2)]
            d = rings[nxt][j]
            tris.append((a, b, c))
            tris.append((a, c, d))
    return tris


def sphere_triangles(centre: Point3Tuple, radius: float, *, tolerance: float) -> list[Triangle3]:
    """Approximate a sphere with latitude-longitude triangles."""
    rings = min(64, max(8, segments_for_circle(radius, tolerance) // 2))
    segs = rings * 2
    tris: list[Triangle3] = []
    for i in range(rings):
        theta0 = pi * i / rings
        theta1 = pi * (i + 1) / rings
        for j in range(segs):
            phi0 = 2 * pi * j / segs
            phi1 = 2 * pi * (j + 1) / segs
            pts: list[Point3] = []
            for theta, phi in ((theta0, phi0), (theta1, phi0), (theta1, phi1), (theta0, phi1)):
                pts.append(
                    _add(
                        centre,
                        (
                            radius * sin(theta) * cos(phi),
                            radius * sin(theta) * sin(phi),
                            radius * cos(theta),
                        ),
                    )
                )
            if pts[0] != pts[1] and pts[1] != pts[2]:
                tris.append((pts[0], pts[1], pts[2]))
            if pts[0] != pts[2] and pts[2] != pts[3]:
                tris.append((pts[0], pts[2], pts[3]))
    return tris


def _map2(point: Point2, origin: Point3Tuple, u: Point3Tuple, v: Point3Tuple) -> Point3Tuple:
    return _add(origin, _add(_scale(u, point[0]), _scale(v, point[1])))


def _add(a: Point3Tuple, b: Point3Tuple) -> Point3Tuple:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a: Point3Tuple, scale: float) -> Point3Tuple:
    return (a[0] * scale, a[1] * scale, a[2] * scale)


def _dot(a: Point3Tuple, b: Point3Tuple) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Point3Tuple, b: Point3Tuple) -> Point3Tuple:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _normalised(a: Point3Tuple) -> Point3Tuple:
    length = _dot(a, a) ** 0.5
    if length == 0:
        raise ValueError("zero-length vector")
    return (a[0] / length, a[1] / length, a[2] / length)


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


def validate_tolerance(tolerance: float) -> float:
    return positive_tolerance(tolerance)


def validate_positive(value: float, name: str) -> float:
    return positive(value, name)


def box_mesh(plane: Plane3, *, width: float, depth: float, height: float) -> Mesh3:
    from cady.geometry.mesh import Mesh3

    width = validate_positive(width, "width")
    depth = validate_positive(depth, "depth")
    height = validate_positive(height, "height")
    z = scale3(plane.normal, height)
    vertices = (
        plane.point(0.0, 0.0),
        plane.point(width, 0.0),
        plane.point(width, depth),
        plane.point(0.0, depth),
        add3(plane.point(0.0, 0.0), z),
        add3(plane.point(width, 0.0), z),
        add3(plane.point(width, depth), z),
        add3(plane.point(0.0, depth), z),
    )
    faces = (
        (0, 2, 1),
        (0, 3, 2),
        (4, 5, 6),
        (4, 6, 7),
        (0, 1, 5),
        (0, 5, 4),
        (1, 2, 6),
        (1, 6, 5),
        (2, 3, 7),
        (2, 7, 6),
        (3, 0, 4),
        (3, 4, 7),
    )
    return Mesh3(vertices, faces)


def cylinder_mesh(
    plane: Plane3,
    *,
    radius: float,
    height: float,
    tolerance: float,
) -> Mesh3:
    from cady.geometry.mesh import Mesh3

    radius = validate_positive(radius, "radius")
    height = validate_positive(height, "height")
    tolerance = validate_tolerance(tolerance)
    segments = segments_for_circle(radius, tolerance)
    top_offset = scale3(plane.normal, height)
    bottom = tuple(
        plane.point(
            radius * cos(2.0 * pi * index / segments),
            radius * sin(2.0 * pi * index / segments),
        )
        for index in range(segments)
    )
    top = tuple(add3(vertex, top_offset) for vertex in bottom)
    bottom_centre = plane.origin
    top_centre = add3(plane.origin, top_offset)
    vertices = bottom + top + (bottom_centre, top_centre)
    bottom_index = segments * 2
    top_index = bottom_index + 1
    faces: list[tuple[int, int, int]] = []
    for index in range(segments):
        next_index = (index + 1) % segments
        faces.append((bottom_index, next_index, index))
        faces.append((top_index, segments + index, segments + next_index))
        faces.append((index, next_index, segments + next_index))
        faces.append((index, segments + next_index, segments + index))
    return Mesh3(vertices, tuple(faces))


def sphere_mesh(plane: Plane3, *, radius: float, tolerance: float) -> Mesh3:
    radius = validate_positive(radius, "radius")
    tolerance = validate_tolerance(tolerance)
    triangles = tuple(
        tuple((float(point[0]), float(point[1]), float(point[2])) for point in triangle)
        for triangle in sphere_triangles(plane.origin, radius, tolerance=tolerance)
    )
    return mesh_from_triangles(triangles)  # type: ignore[arg-type]


__all__ = [
    "CompatibilityReport",
    "GuideCoverage",
    "KeepSide",
    "LinesplanCurve",
    "LinesplanNetwork",
    "LoftMesh",
    "RejectedLinesplanCurve",
    "basis_for_axis",
    "boundary_edges",
    "boundary_edges_from_faces",
    "box_mesh",
    "classify_linesplan_curves",
    "close_boundary",
    "close_planar_cap",
    "close_to_plane",
    "closed_polyline_mesh2",
    "closed_polyline_mesh3",
    "coerce_mesh",
    "compact_mesh_data",
    "cut_mesh_by_plane",
    "cylinder_mesh",
    "dedupe_closed",
    "edge_loops",
    "extrusion_mesh",
    "extrusion_triangles",
    "loft_section_polylines",
    "mesh_from_triangles",
    "mesh_linesplan_network",
    "prism_triangles",
    "prune_dangling_edges",
    "region_loops_from_region",
    "region_mesh",
    "revolution_triangles",
    "segments_for_circle",
    "sphere_mesh",
    "sphere_triangles",
    "stitch_segments",
    "surface_region_mesh",
    "triangulate_polygon",
    "validate_positive",
    "validate_tolerance",
    "wireframe_mesh",
]
