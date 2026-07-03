"""Linesplan station geometry and meshing."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from math import dist, isfinite
from pathlib import Path
from statistics import median
from typing import TypeAlias, cast

from cady.errors import ReadError
from cady.files import dxf
from cady.geometry import Mesh3, Polyline3, Wireframe3
from cady.operations.meshes import classify_linesplan_curves
from cady.operations.meshing import closed_polyline_mesh3

_Point3: TypeAlias = tuple[float, float, float]
_Face: TypeAlias = tuple[int, int, int]
_Edge: TypeAlias = tuple[int, int]
_NodeArray: TypeAlias = tuple[tuple[_Point3, ...], ...]

_DEFAULT_NODES_ON_POLYLINE = 48
_DEFAULT_TOLERANCE = 1e-3
_DEFAULT_SNAP_TOLERANCE = 1000.0


@dataclass(frozen=True, slots=True)
class Linesplan:
    """Cleaned, mirrored station polylines for a vessel linesplan."""

    polylines: tuple[Polyline3, ...]
    nodes_on_polyline: int = _DEFAULT_NODES_ON_POLYLINE

    def __init__(
        self,
        polylines: Iterable[Polyline3],
        *,
        nodes_on_polyline: int = _DEFAULT_NODES_ON_POLYLINE,
    ) -> None:
        polylines = tuple(polylines)
        if len(polylines) < 2:
            raise ValueError("Linesplan requires at least two station polylines")
        nodes_on_polyline = _validate_nodes_on_polyline(nodes_on_polyline)
        object.__setattr__(self, "polylines", polylines)
        object.__setattr__(self, "nodes_on_polyline", nodes_on_polyline)

    @classmethod
    def from_dxf(
        cls,
        path: str | Path,
        *,
        nodes_on_polyline: int = _DEFAULT_NODES_ON_POLYLINE,
        tolerance: float = _DEFAULT_TOLERANCE,
        snap_tolerance: float = _DEFAULT_SNAP_TOLERANCE,
    ) -> Linesplan:
        """Read station lines from a DXF and return cleaned station polylines."""
        nodes_on_polyline = _validate_nodes_on_polyline(nodes_on_polyline)
        _validate_tolerance(tolerance, "tolerance")
        _validate_tolerance(snap_tolerance, "snap_tolerance")

        network = classify_linesplan_curves(dxf.read_curves(path), tolerance=tolerance)
        station_polylines = tuple(Polyline3(curve.vertices) for curve in network.sections)
        if len(station_polylines) < 2:
            raise ReadError("DXF contained fewer than two station line curves")

        station_lines = _process_station_lines(
            station_polylines,
            snap_tolerance,
            tolerance=tolerance,
        )
        return cls(
            _mirror_station_lines(station_lines, tolerance=tolerance),
            nodes_on_polyline=nodes_on_polyline,
        )

    def to_grid_wireframe(
        self,
        *,
        nodes_on_polyline: int | None = None,
        nodes_per_station: int | None = None,
        tolerance: float = _DEFAULT_TOLERANCE,
    ) -> Wireframe3:
        """Sample stations into an equal-width grid wireframe."""
        nodes_on_polyline = _resolve_nodes_on_polyline(
            nodes_on_polyline,
            nodes_per_station,
            default=self.nodes_on_polyline,
        )
        _validate_tolerance(tolerance, "tolerance")

        nodes = _node_array(self.polylines, nodes_on_polyline, tolerance=tolerance)
        vertices = tuple(point for row in nodes for point in row)
        return Wireframe3.from_edges(vertices, _grid_edges(len(nodes), nodes_on_polyline))

    def to_mesh(
        self,
        *,
        nodes_on_polyline: int | None = None,
        nodes_per_station: int | None = None,
        tolerance: float = _DEFAULT_TOLERANCE,
    ) -> Mesh3:
        """Return a closed triangular mesh from the station grid."""
        nodes_on_polyline = _resolve_nodes_on_polyline(
            nodes_on_polyline,
            nodes_per_station,
            default=self.nodes_on_polyline,
        )
        _validate_tolerance(tolerance, "tolerance")

        grid = self.to_grid_wireframe(
            nodes_on_polyline=nodes_on_polyline,
            tolerance=tolerance,
        )
        front_row = grid.vertices[:nodes_on_polyline]
        back_row = tuple(reversed(grid.vertices[-nodes_on_polyline:]))
        faces = _triangular_grid_faces(len(self.polylines), nodes_on_polyline)
        side_mesh = Mesh3(
            grid.vertices,
            faces,
            _face_edges(faces),
        )
        front_cap = closed_polyline_mesh3(
            Polyline3(front_row, closed=True),
            tolerance=tolerance,
            max_edge_length=_cap_max_edge_length(front_row, tolerance=tolerance),
        )
        back_cap = closed_polyline_mesh3(
            Polyline3(back_row, closed=True),
            tolerance=tolerance,
            max_edge_length=_cap_max_edge_length(back_row, tolerance=tolerance),
        )
        closed = _weld_mesh(
            Mesh3.merged((side_mesh, front_cap, back_cap)),
            tolerance=tolerance,
        )
        return Mesh3(closed.vertices, closed.faces, _face_edges(closed.faces))


def _process_station_lines(
    polylines: Iterable[Polyline3],
    snap_tolerance: float,
    *,
    tolerance: float,
) -> tuple[Polyline3, ...]:
    rows: list[tuple[_Point3, ...]] = [
        _dedupe(
            (
                _clean_point(point, tolerance=tolerance)
                for point in _polyline_array(polyline, tolerance=tolerance)
            ),
            tolerance=tolerance,
        )
        for polyline in polylines
    ]
    if any(len(row) < 2 for row in rows):
        raise ValueError("each station line must contain at least two distinct points")

    connected: list[tuple[_Point3, ...]] = []
    while rows:
        row = rows.pop(0)
        while True:
            match_index = None
            match_row: tuple[_Point3, ...] | None = None

            for index, candidate in enumerate(rows):
                if len(row) == len(candidate):
                    same = max(dist(a, b) for a, b in zip(row, candidate, strict=True))
                    flipped = max(dist(a, b) for a, b in zip(row, reversed(candidate), strict=True))
                    if same <= tolerance or flipped <= tolerance:
                        match_index = index
                        match_row = row
                        break

                joins: list[tuple[_Point3, ...]] = []
                if dist(row[-1], candidate[0]) <= snap_tolerance:
                    joins.append(row + candidate[1:])
                if dist(row[-1], candidate[-1]) <= snap_tolerance:
                    joins.append(row + tuple(reversed(candidate[:-1])))
                if dist(row[0], candidate[-1]) <= snap_tolerance:
                    joins.append(candidate[:-1] + row)
                if dist(row[0], candidate[0]) <= snap_tolerance:
                    joins.append(tuple(reversed(candidate[1:])) + row)
                if len(joins) == 1:
                    match_index = index
                    match_row = joins[0]
                    break

                best_snap: tuple[float, tuple[_Point3, ...]] | None = None
                for source, target in ((candidate, row), (row, candidate)):
                    for endpoint_index in (0, -1):
                        endpoint = source[endpoint_index]
                        source_row = source if endpoint_index == 0 else tuple(reversed(source))

                        for segment_index, (start, end) in enumerate(
                            zip(target, target[1:], strict=False)
                        ):
                            segment = (
                                end[0] - start[0],
                                end[1] - start[1],
                                end[2] - start[2],
                            )
                            length_squared = (
                                segment[0] * segment[0]
                                + segment[1] * segment[1]
                                + segment[2] * segment[2]
                            )
                            if length_squared == 0.0:
                                continue

                            offset = (
                                endpoint[0] - start[0],
                                endpoint[1] - start[1],
                                endpoint[2] - start[2],
                            )
                            position = (
                                offset[0] * segment[0]
                                + offset[1] * segment[1]
                                + offset[2] * segment[2]
                            ) / length_squared
                            if not 0.0 < position < 1.0:
                                continue

                            snap_point = _clean_point(
                                (
                                    start[0] + segment[0] * position,
                                    start[1] + segment[1] * position,
                                    start[2] + segment[2] * position,
                                ),
                                tolerance=tolerance,
                            )
                            distance = dist(endpoint, snap_point)
                            if distance > snap_tolerance:
                                continue

                            snapped = (
                                target[: segment_index + 1]
                                + (snap_point,)
                                + source_row
                                + target[segment_index + 1 :]
                            )
                            if best_snap is None or distance < best_snap[0]:
                                best_snap = (distance, snapped)

                if best_snap is not None:
                    match_index = index
                    match_row = best_snap[1]
                    break

            if match_index is None or match_row is None:
                break

            row = _dedupe(match_row, tolerance=tolerance)
            del rows[match_index]

        connected.append(row)

    connected.sort(key=lambda line: median(point[0] for point in line))
    if len(connected) < 2:
        raise ValueError("linesplan mesh requires at least two station lines")
    return tuple(Polyline3(row) for row in connected)


def _mirror_station_lines(
    polylines: Iterable[Polyline3],
    *,
    tolerance: float,
) -> tuple[Polyline3, ...]:
    mirrored: list[Polyline3] = []
    for polyline in polylines:
        points = [
            _clean_point(point, tolerance=tolerance)
            for point in _polyline_array(polyline, tolerance=tolerance)
        ]
        if points[-1][2] > points[0][2]:
            points = list(reversed(points))

        mirrored_points = [
            _clean_point((point[0], -point[1], point[2]), tolerance=tolerance) for point in points
        ]
        mirrored_points = list(reversed(mirrored_points))
        if dist(points[-1], mirrored_points[0]) <= tolerance:
            mirrored_points = mirrored_points[1:]

        mirrored.append(Polyline3((*points, *mirrored_points)))
    return tuple(mirrored)


def _node_array(
    polylines: Iterable[Polyline3],
    nodes_on_polyline: int,
    *,
    tolerance: float,
) -> _NodeArray:
    rows: list[tuple[_Point3, ...]] = []
    for polyline in polylines:
        points = _dedupe(
            (
                _clean_point(point, tolerance=tolerance)
                for point in _polyline_array(polyline, tolerance=tolerance)
            ),
            tolerance=tolerance,
        )
        if len(points) < 2:
            raise ValueError("each station line must contain at least two distinct points")
        if points[-1][2] > points[0][2]:
            points = tuple(reversed(points))

        lengths = tuple(dist(start, end) for start, end in zip(points, points[1:], strict=False))
        total = sum(lengths)
        if total <= tolerance:
            raise ValueError("each station line must have non-zero length")

        row: list[_Point3] = []
        for node_index in range(nodes_on_polyline):
            target = total * node_index / (nodes_on_polyline - 1)
            walked = 0.0
            for start, end, length in zip(points, points[1:], lengths, strict=True):
                next_walked = walked + length
                if target <= next_walked or end == points[-1]:
                    ratio = 0.0 if length == 0.0 else (target - walked) / length
                    row.append(
                        (
                            start[0] + (end[0] - start[0]) * ratio,
                            start[1] + (end[1] - start[1]) * ratio,
                            start[2] + (end[2] - start[2]) * ratio,
                        )
                    )
                    break
                walked = next_walked

        nodes = tuple(row)
        x = float(median(point[0] for point in nodes))
        rows.append(tuple((x, point[1], point[2]) for point in nodes))

    if len(rows) < 2:
        raise ValueError("linesplan mesh requires at least two station lines")
    return tuple(rows)


def _grid_edges(row_count: int, width: int) -> tuple[_Edge, ...]:
    edges: set[_Edge] = set()
    for row_index in range(row_count):
        start = row_index * width
        for column_index in range(width - 1):
            edges.add((start + column_index, start + column_index + 1))
        edges.add((start, start + width - 1))

    for row_index in range(row_count - 1):
        start = row_index * width
        next_start = (row_index + 1) * width
        for column_index in range(width):
            edges.add((start + column_index, next_start + column_index))

    return tuple(sorted(edges))


def _triangular_grid_faces(row_count: int, width: int) -> tuple[_Face, ...]:
    faces: list[_Face] = []
    for row_index in range(row_count - 1):
        start = row_index * width
        next_start = (row_index + 1) * width
        for column_index in range(width - 1):
            a = start + column_index
            b = next_start + column_index
            c = next_start + column_index + 1
            d = start + column_index + 1
            faces.append((a, b, c))
            faces.append((a, c, d))

        a = start
        b = start + width - 1
        c = next_start + width - 1
        d = next_start
        faces.append((a, b, c))
        faces.append((a, c, d))

    return tuple(faces)


def _face_edges(faces: Iterable[Sequence[int]]) -> tuple[_Edge, ...]:
    edges: set[_Edge] = set()
    for face in faces:
        for start, end in zip(face, (*face[1:], face[0]), strict=True):
            edges.add((min(start, end), max(start, end)))
    return tuple(sorted(edges))


def _cap_max_edge_length(
    points: Sequence[_Point3],
    *,
    tolerance: float,
) -> float | None:
    lengths: list[float] = []
    for start, end in zip(points, (*points[1:], points[0]), strict=True):
        length = dist(start, end)
        if length > tolerance:
            lengths.append(length)
    if not lengths:
        return None
    return max(lengths) * 1.000001


def _weld_mesh(mesh: Mesh3, *, tolerance: float) -> Mesh3:
    index_by_point: dict[tuple[int, int, int], int] = {}
    vertices: list[_Point3] = []
    remap: list[int] = []
    for x, y, z in mesh.vertices:
        if abs(y) <= tolerance:
            y = 0.0
        key = (round(x / tolerance), round(y / tolerance), round(z / tolerance))
        if key not in index_by_point:
            index_by_point[key] = len(vertices)
            vertices.append((x, y, z))
        remap.append(index_by_point[key])

    welded_faces: list[_Face] = []
    for face in mesh.faces:
        mapped: list[int] = []
        for index in face:
            new_index = remap[index]
            if not mapped or mapped[-1] != new_index:
                mapped.append(new_index)
        if len(mapped) > 1 and mapped[0] == mapped[-1]:
            mapped.pop()
        if len(set(mapped)) == 3:
            welded_faces.append(cast(_Face, tuple(mapped)))

    welded_edges: set[_Edge] = set()
    for a, b in mesh.edges:
        start, end = remap[a], remap[b]
        if start != end:
            welded_edges.add((min(start, end), max(start, end)))

    return Mesh3(tuple(vertices), tuple(welded_faces), tuple(sorted(welded_edges)))


def _polyline_array(polyline: Polyline3, *, tolerance: float) -> tuple[_Point3, ...]:
    return tuple(_plain_point(point) for point in polyline.to_array(tolerance=tolerance))


def _plain_point(point: object) -> _Point3:
    coordinates = cast(Sequence[float], point)
    return (float(coordinates[0]), float(coordinates[1]), float(coordinates[2]))


def _clean_point(point: object, *, tolerance: float) -> _Point3:
    x, y, z = _plain_point(point)
    if abs(y) <= tolerance:
        y = 0.0
    return (x, y, z)


def _dedupe(points: Iterable[_Point3], *, tolerance: float) -> tuple[_Point3, ...]:
    kept: list[_Point3] = []
    for point in points:
        if not kept or dist(point, kept[-1]) > tolerance:
            kept.append(point)
    return tuple(kept)


def _resolve_nodes_on_polyline(
    nodes_on_polyline: int | None,
    nodes_per_station: int | None,
    *,
    default: int,
) -> int:
    if nodes_on_polyline is not None and nodes_per_station is not None:
        raise ValueError("use either nodes_on_polyline or nodes_per_station, not both")
    if nodes_on_polyline is not None:
        return _validate_nodes_on_polyline(nodes_on_polyline)
    if nodes_per_station is not None:
        return _validate_nodes_on_polyline(nodes_per_station)
    return _validate_nodes_on_polyline(default)


def _validate_nodes_on_polyline(nodes_on_polyline: object) -> int:
    if not isinstance(nodes_on_polyline, int) or isinstance(nodes_on_polyline, bool):
        raise TypeError("nodes_on_polyline must be an integer")
    if nodes_on_polyline < 2:
        raise ValueError("nodes_on_polyline must be at least 2")
    return nodes_on_polyline


def _validate_tolerance(tolerance: float, name: str) -> None:
    if tolerance <= 0.0 or not isfinite(tolerance):
        raise ValueError(f"{name} must be positive")


__all__ = ["Linesplan"]
