"""Vessel linesplan station geometry and meshing."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from math import ceil, dist, isfinite
from pathlib import Path
from statistics import median
from typing import TYPE_CHECKING, TypeAlias, cast

from cady.errors import ReadError
from cady.files import dxf
from cady.geometry import Mesh3, Polyline3, Wireframe3
from cady.operations.linesplan_meshing import classify_linesplan_curves

if TYPE_CHECKING:
    from cady.view import Camera, DisplayStyle, Light
    from cady.view.style import RenderMode
    from cady.view.viewer import Projection

_Point3: TypeAlias = tuple[float, float, float]
_Face: TypeAlias = tuple[int, ...]
_Edge: TypeAlias = tuple[int, int]
_PolylineGroup: TypeAlias = tuple[Polyline3, ...]
_PolylineGroups: TypeAlias = tuple[_PolylineGroup, _PolylineGroup]
_NodeArray: TypeAlias = tuple[tuple[_Point3, ...], ...]

_DEFAULT_NODES_ON_POLYLINE = 48
_DEFAULT_CLASSIFICATION_TOLERANCE = 1e-3
_MIN_STATION_FRAGMENT_LENGTH = 1.0
_KEEL_DISCONTINUITY_ANGLE_DEGREES = 60.0
_MIRROR_PLANE_ORIGIN: _Point3 = (0.0, 0.0, 0.0)
_MIRROR_PLANE_NORMAL: _Point3 = (0.0, 1.0, 0.0)


@dataclass(frozen=True, slots=True)
class LinesplanMeshSettings:
    """Resolved tolerances and spacing used to mesh a linesplan."""

    dxf_snap_tolerance: float
    mesh_geometry_tolerance: float
    mesh_snap_tolerance: float
    node_spacing: float
    short_projection_ratio: float


@dataclass(frozen=True, slots=True)
class _LoftedMeshPatch:
    group_index: int
    polylines: _PolylineGroup
    nodes: _NodeArray
    mesh: Mesh3
    yellow_nodes: tuple[_BoundaryNode, ...] = ()
    green_nodes: tuple[_BoundaryNode, ...] = ()


@dataclass(frozen=True, slots=True)
class _BoundaryNode:
    row_index: int
    point: _Point3


@dataclass(frozen=True, slots=True)
class Linesplan:
    """Cleaned station polylines for a vessel linesplan."""

    polylines: tuple[Polyline3, ...]
    nodes_on_polyline: int
    settings: LinesplanMeshSettings
    polyline_groups: _PolylineGroups

    def __init__(
        self,
        polylines: Iterable[Polyline3],
        *,
        nodes_on_polyline: int = _DEFAULT_NODES_ON_POLYLINE,
        settings: LinesplanMeshSettings | None = None,
        polyline_groups: _PolylineGroups | None = None,
    ) -> None:
        polylines = tuple(polylines)
        if len(polylines) < 2:
            raise ValueError("Linesplan requires at least two station polylines")
        nodes_on_polyline = _validate_nodes_on_polyline(nodes_on_polyline)
        if settings is None:
            settings = _resolve_mesh_settings(polylines)
        else:
            _validate_mesh_settings(settings)
        if polyline_groups is None:
            polyline_groups = _split_station_lines(
                polylines,
                tolerance=settings.mesh_geometry_tolerance,
            )

        object.__setattr__(self, "polylines", polylines)
        object.__setattr__(self, "nodes_on_polyline", nodes_on_polyline)
        object.__setattr__(self, "settings", settings)
        object.__setattr__(self, "polyline_groups", polyline_groups)

    @classmethod
    def from_dxf(
        cls,
        path: str | Path,
        *,
        nodes_on_polyline: int = _DEFAULT_NODES_ON_POLYLINE,
        tolerance: float = _DEFAULT_CLASSIFICATION_TOLERANCE,
        dxf_snap_tolerance: float | None = None,
        mesh_geometry_tolerance: float | None = None,
        mesh_snap_tolerance: float | None = None,
        node_spacing: float | None = None,
        short_projection_ratio: float | None = None,
        snap_tolerance: float | None = None,
    ) -> Linesplan:
        """Read station lines from a DXF and return cleaned station polylines."""
        nodes_on_polyline = _validate_nodes_on_polyline(nodes_on_polyline)
        _validate_tolerance(tolerance, "tolerance")
        if snap_tolerance is not None and dxf_snap_tolerance is not None:
            raise ValueError("use either dxf_snap_tolerance or snap_tolerance, not both")
        if dxf_snap_tolerance is None:
            dxf_snap_tolerance = snap_tolerance

        network = classify_linesplan_curves(dxf.read_curves(path), tolerance=tolerance)
        station_polylines = tuple(Polyline3(curve.vertices) for curve in network.sections)
        if len(station_polylines) < 2:
            raise ReadError("DXF contained fewer than two station line curves")

        settings = _resolve_mesh_settings(
            station_polylines,
            dxf_snap_tolerance=dxf_snap_tolerance,
            mesh_geometry_tolerance=mesh_geometry_tolerance,
            mesh_snap_tolerance=mesh_snap_tolerance,
            node_spacing=node_spacing,
            short_projection_ratio=short_projection_ratio,
        )
        connected_station_polylines = _process_station_lines(
            station_polylines,
            settings.dxf_snap_tolerance,
            tolerance=settings.mesh_geometry_tolerance,
        )
        prepared_station_polylines = _prepare_station_lines(
            connected_station_polylines,
            tolerance=settings.mesh_geometry_tolerance,
        )
        if len(prepared_station_polylines) < 2:
            raise ReadError("DXF contained fewer than two connected station line curves")

        polyline_groups = _split_station_lines(
            prepared_station_polylines,
            tolerance=settings.mesh_geometry_tolerance,
        )
        return cls(
            prepared_station_polylines,
            nodes_on_polyline=nodes_on_polyline,
            settings=settings,
            polyline_groups=polyline_groups,
        )

    def to_wireframe(self) -> Wireframe3:
        """Return the cleaned connected station lines as a wireframe."""
        return Wireframe3.from_polylines(self.polylines)

    def view(
        self,
        *,
        name: str | None = None,
        title: str | None = None,
        camera: Camera | None = None,
        style: DisplayStyle | None = None,
        light: Light | None = None,
        color: tuple[float, float, float] | None = None,
        render_mode: RenderMode | None = None,
        projection: Projection = "orthographic",
        center: bool = True,
        tolerance: float = _DEFAULT_CLASSIFICATION_TOLERANCE,
    ) -> None:
        """View the cleaned station lines."""
        self.to_wireframe().view(
            name=name,
            title=title,
            camera=camera,
            style=style,
            light=light,
            color=color,
            render_mode=render_mode,
            projection=projection,
            center=center,
            tolerance=tolerance,
        )

    def to_grid_wireframe(
        self,
        *,
        nodes_on_polyline: int | None = None,
        nodes_per_station: int | None = None,
        tolerance: float | None = None,
    ) -> Wireframe3:
        """Sample cleaned stations into an equal-width grid wireframe."""
        nodes_on_polyline = _resolve_nodes_on_polyline(
            nodes_on_polyline,
            nodes_per_station,
            default=self.nodes_on_polyline,
        )
        tolerance = (
            self.settings.mesh_geometry_tolerance
            if tolerance is None
            else _validate_tolerance(tolerance, "tolerance")
        )

        nodes = _node_array(self.polylines, nodes_on_polyline, tolerance=tolerance)
        vertices = tuple(point for row in nodes for point in row)
        return Wireframe3.from_edges(vertices, _grid_edges(len(nodes), nodes_on_polyline))

    def to_mesh(
        self,
        *,
        node_spacing: float | None = None,
        nodes_on_polyline: int | None = None,
        nodes_per_station: int | None = None,
        tolerance: float | None = None,
        snap_tolerance: float | None = None,
        short_projection_ratio: float | None = None,
    ) -> Mesh3:
        """Return a closed triangular mesh from the station lines."""
        mesh_tolerance = (
            self.settings.mesh_geometry_tolerance
            if tolerance is None
            else _validate_tolerance(tolerance, "tolerance")
        )
        snap_tolerance = (
            self.settings.mesh_snap_tolerance
            if snap_tolerance is None
            else _validate_tolerance(snap_tolerance, "snap_tolerance")
        )
        short_projection_ratio = (
            self.settings.short_projection_ratio
            if short_projection_ratio is None
            else _validate_ratio(short_projection_ratio, "short_projection_ratio")
        )
        node_spacing = _resolve_node_spacing(
            self.polylines,
            node_spacing,
            nodes_on_polyline,
            nodes_per_station,
            default=self.settings.node_spacing,
        )

        station_green_points = _station_end_points(self.polylines, tolerance=mesh_tolerance)
        lofted_mesh_patches = tuple(
            _mark_mesh_boundary_nodes(
                patch,
                station_green_points,
                tolerance=mesh_tolerance,
            )
            for patch in _loft_polyline_groups(
                self.polyline_groups,
                node_spacing=node_spacing,
                tolerance=mesh_tolerance,
            )
        )
        extension_meshes = tuple(
            mesh
            for patch in lofted_mesh_patches
            for nodes in (patch.yellow_nodes, patch.green_nodes)
            for mesh in _boundary_extension_meshes(
                nodes,
                node_spacing=node_spacing,
                tolerance=mesh_tolerance,
                short_projection_ratio=short_projection_ratio,
            )
        )
        half_meshes = _merge_boundary_extensions(lofted_mesh_patches, extension_meshes)
        mirrored_meshes = tuple(
            mesh.mirror(_MIRROR_PLANE_ORIGIN, _MIRROR_PLANE_NORMAL) for mesh in half_meshes
        )
        mesh_patches = (*half_meshes, *mirrored_meshes)
        keel_cap_mesh = _keel_end_cap_mesh(_keel_end_rows(_keel_boundary_rows(lofted_mesh_patches)))
        combined_mesh = _weld_mesh(
            Mesh3.merged((*mesh_patches, keel_cap_mesh)),
            tolerance=mesh_tolerance,
        )
        closed_mesh = _try_close_mesh(combined_mesh, tolerance=mesh_tolerance)
        triangulation_input = _split_quad_faces(closed_mesh)
        return _triangulate_mesh_faces(
            triangulation_input,
            tolerance=mesh_tolerance,
        ).snap_close_nodes(tolerance=snap_tolerance)


def _resolve_mesh_settings(
    station_lines: Iterable[Polyline3],
    *,
    dxf_snap_tolerance: float | None = None,
    mesh_geometry_tolerance: float | None = None,
    mesh_snap_tolerance: float | None = None,
    node_spacing: float | None = None,
    short_projection_ratio: float | None = None,
) -> LinesplanMeshSettings:
    domain_length = _station_domain_length(station_lines)
    settings = LinesplanMeshSettings(
        dxf_snap_tolerance=_setting_value(
            dxf_snap_tolerance,
            domain_length * 0.0056,
            "dxf_snap_tolerance",
        ),
        mesh_geometry_tolerance=_setting_value(
            mesh_geometry_tolerance,
            max(1e-6, domain_length * 5.6e-9),
            "mesh_geometry_tolerance",
        ),
        mesh_snap_tolerance=_setting_value(
            mesh_snap_tolerance,
            domain_length * 0.0028,
            "mesh_snap_tolerance",
        ),
        node_spacing=_setting_value(
            node_spacing,
            domain_length * 0.0112,
            "node_spacing",
        ),
        short_projection_ratio=_ratio_setting_value(
            short_projection_ratio,
            0.3,
            "short_projection_ratio",
        ),
    )
    _validate_mesh_settings(settings)
    return settings


def _validate_mesh_settings(settings: LinesplanMeshSettings) -> None:
    _validate_tolerance(settings.dxf_snap_tolerance, "dxf_snap_tolerance")
    _validate_tolerance(settings.mesh_geometry_tolerance, "mesh_geometry_tolerance")
    _validate_tolerance(settings.mesh_snap_tolerance, "mesh_snap_tolerance")
    _validate_tolerance(settings.node_spacing, "node_spacing")
    _validate_ratio(settings.short_projection_ratio, "short_projection_ratio")


def _setting_value(value: float | None, default: float, name: str) -> float:
    return _validate_tolerance(default if value is None else value, name)


def _ratio_setting_value(value: float | None, default: float, name: str) -> float:
    return _validate_ratio(default if value is None else value, name)


def _station_domain_length(station_lines: Iterable[Polyline3]) -> float:
    xs = tuple(point[0] for polyline in station_lines for point in polyline.points())
    if not xs:
        raise ValueError("station_lines must have a positive x span")
    span = max(xs) - min(xs)
    if span <= 0.0:
        raise ValueError("station_lines must have a positive x span")
    return span


def _process_station_lines(
    polylines: Iterable[Polyline3],
    snap_tolerance: float,
    *,
    tolerance: float,
) -> tuple[Polyline3, ...]:
    rows: list[tuple[_Point3, ...]] = []
    for polyline in polylines:
        row = _dedupe(
            (
                _clean_point(point, tolerance=tolerance)
                for point in _polyline_array(polyline, tolerance=tolerance)
            ),
            tolerance=tolerance,
        )
        if len(row) >= 2 and _polyline_length(row) > _MIN_STATION_FRAGMENT_LENGTH:
            rows.append(row)

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


def _prepare_station_lines(
    polylines: Iterable[Polyline3],
    *,
    tolerance: float,
) -> tuple[Polyline3, ...]:
    return tuple(_prepare_station_line(polyline, tolerance=tolerance) for polyline in polylines)


def _prepare_station_line(polyline: Polyline3, *, tolerance: float) -> Polyline3:
    points = _dedupe(
        (
            _clean_point(point, tolerance=tolerance)
            for point in _polyline_array(polyline, tolerance=tolerance)
        ),
        tolerance=tolerance,
    )
    points = _trim_after_top_positive_y(points, tolerance=tolerance)
    prepared = Polyline3(points)
    if prepared.end[2] > prepared.start[2]:
        prepared = prepared.reverse()
    return prepared


def _split_station_lines(
    polylines: Iterable[Polyline3],
    *,
    tolerance: float,
) -> _PolylineGroups:
    positive_y_top: list[Polyline3] = []
    discontinuity_top: list[Polyline3] = []

    for polyline in polylines:
        points = _dedupe(
            (
                _clean_point(point, tolerance=tolerance)
                for point in _polyline_array(polyline, tolerance=tolerance)
            ),
            tolerance=tolerance,
        )
        discontinuity_index = _top_discontinuity_index(points, tolerance=tolerance)
        if discontinuity_index is None:
            positive_y_top.append(Polyline3(points))
            continue

        yellow_top_points = points[: discontinuity_index + 1]
        red_top_points = points[discontinuity_index:]
        if len(yellow_top_points) >= 2:
            positive_y_top.append(Polyline3(yellow_top_points))
        if len(red_top_points) >= 2:
            discontinuity_top.append(Polyline3(red_top_points))

    return (tuple(positive_y_top), tuple(discontinuity_top))


def _top_discontinuity_index(
    points: tuple[_Point3, ...],
    *,
    tolerance: float,
) -> int | None:
    discontinuities = Polyline3(points).discontinuities(
        min_angle_degrees=_KEEL_DISCONTINUITY_ANGLE_DEGREES,
        min_segment_length=tolerance,
    )
    if not discontinuities:
        return None

    discontinuity_indices: list[int] = []
    for discontinuity in discontinuities:
        point = _clean_point(discontinuity, tolerance=tolerance)
        index, distance = min(
            ((index, dist(candidate, point)) for index, candidate in enumerate(points)),
            key=lambda item: item[1],
        )
        if distance <= tolerance:
            discontinuity_indices.append(index)

    if not discontinuity_indices:
        return None
    return max(discontinuity_indices, key=lambda index: points[index][2])


def _trim_after_top_positive_y(
    points: tuple[_Point3, ...],
    *,
    tolerance: float,
) -> tuple[_Point3, ...]:
    top_index = _top_positive_y_index(points, tolerance=tolerance)
    if top_index is None or top_index == 0 or top_index == len(points) - 1:
        return points
    return points[: top_index + 1]


def _top_positive_y_index(
    points: tuple[_Point3, ...],
    *,
    tolerance: float,
) -> int | None:
    positive_y_points = (
        (index, point) for index, point in enumerate(points) if point[1] > tolerance
    )
    top = max(positive_y_points, key=lambda item: item[1][2], default=None)
    if top is None:
        return None
    return top[0]


def _station_end_points(
    polylines: Iterable[Polyline3],
    *,
    tolerance: float,
) -> tuple[_Point3, ...]:
    return tuple(_clean_point(polyline.end, tolerance=tolerance) for polyline in polylines)


def _loft_polyline_groups(
    polyline_groups: Iterable[_PolylineGroup],
    *,
    node_spacing: float,
    tolerance: float,
) -> tuple[_LoftedMeshPatch, ...]:
    patches: list[_LoftedMeshPatch] = []
    for group_index, polyline_group in enumerate(polyline_groups):
        if polyline_group:
            nodes = _node_array_for_spacing(
                polyline_group,
                node_spacing=node_spacing,
                tolerance=tolerance,
            )
            patches.append(
                _LoftedMeshPatch(
                    group_index=group_index,
                    polylines=polyline_group,
                    nodes=nodes,
                    mesh=_mesh_node_array(nodes),
                )
            )
    return tuple(patches)


def _mark_mesh_boundary_nodes(
    patch: _LoftedMeshPatch,
    green_points: Iterable[_Point3],
    *,
    tolerance: float,
) -> _LoftedMeshPatch:
    green_points = tuple(green_points)
    end_column = len(patch.nodes[0]) - 1
    yellow_nodes: tuple[_BoundaryNode, ...] = ()
    if patch.group_index == 0:
        yellow_nodes = tuple(
            _BoundaryNode(row_index, row[0]) for row_index, row in enumerate(patch.nodes)
        )

    green_nodes = tuple(
        _BoundaryNode(row_index, patch.nodes[row_index][end_column])
        for row_index, polyline in enumerate(patch.polylines)
        if _matches_any_point(polyline.end, green_points, tolerance=tolerance)
    )
    return _LoftedMeshPatch(
        group_index=patch.group_index,
        polylines=patch.polylines,
        nodes=patch.nodes,
        mesh=patch.mesh,
        yellow_nodes=yellow_nodes,
        green_nodes=green_nodes,
    )


def _boundary_extension_meshes(
    nodes: Iterable[_BoundaryNode],
    *,
    node_spacing: float,
    tolerance: float,
    short_projection_ratio: float,
) -> tuple[Mesh3, ...]:
    meshes: list[Mesh3] = []
    chain: list[_BoundaryNode] = []
    for node in sorted(nodes, key=lambda item: item.row_index):
        if chain and node.row_index != chain[-1].row_index + 1:
            meshes.append(
                _boundary_extension_mesh(
                    (boundary_node.point for boundary_node in chain),
                    node_spacing=node_spacing,
                    tolerance=tolerance,
                    short_projection_ratio=short_projection_ratio,
                )
            )
            chain = []
        chain.append(node)

    if chain:
        meshes.append(
            _boundary_extension_mesh(
                (boundary_node.point for boundary_node in chain),
                node_spacing=node_spacing,
                tolerance=tolerance,
                short_projection_ratio=short_projection_ratio,
            )
        )
    return tuple(mesh for mesh in meshes if mesh.vertices)


def _boundary_extension_mesh(
    points: Iterable[_Point3],
    *,
    node_spacing: float,
    tolerance: float,
    short_projection_ratio: float,
) -> Mesh3:
    points = tuple(points)
    if len(points) < 2:
        return Mesh3((), ())

    longest_projection = max(abs(point[1]) for point in points)
    short_projection_limit = longest_projection * short_projection_ratio
    vertices: list[_Point3] = []
    columns: list[tuple[int, ...]] = []
    for point in points:
        segment_count = _projection_segment_count(
            point,
            node_spacing=node_spacing,
            short_projection_limit=short_projection_limit,
        )
        column: list[int] = []
        for segment_index in range(segment_count + 1):
            ratio = segment_index / segment_count
            column.append(len(vertices))
            vertices.append(
                (
                    point[0],
                    0.0 if segment_index == segment_count else point[1] * (1.0 - ratio),
                    point[2],
                )
            )
        columns.append(tuple(column))

    faces: list[_Face] = []
    edges: set[_Edge] = set()
    for edge_column in columns:
        for edge in zip(edge_column, edge_column[1:], strict=False):
            edges.add(_edge_key(*edge))
    for left_column, right_column in zip(columns, columns[1:], strict=False):
        _append_projection_faces(left_column, right_column, faces, edges)

    mesh = Mesh3(tuple(vertices), tuple(faces), tuple(sorted(edges)))
    return _weld_mesh(mesh, tolerance=tolerance)


def _projection_segment_count(
    point: _Point3,
    *,
    node_spacing: float,
    short_projection_limit: float,
) -> int:
    projection_distance = abs(point[1])
    if projection_distance < short_projection_limit:
        return 1
    return max(1, ceil(projection_distance / node_spacing))


def _append_projection_faces(
    left_column: tuple[int, ...],
    right_column: tuple[int, ...],
    faces: list[_Face],
    edges: set[_Edge],
) -> None:
    left_segments = len(left_column) - 1
    right_segments = len(right_column) - 1
    left_index = 0
    right_index = 0

    while left_index < left_segments or right_index < right_segments:
        next_left = (
            (left_index + 1) / left_segments
            if left_index < left_segments
            else float("inf")
        )
        next_right = (
            (right_index + 1) / right_segments
            if right_index < right_segments
            else float("inf")
        )
        if abs(next_left - next_right) <= 1e-12:
            face = _clean_face(
                (
                    left_column[left_index],
                    left_column[left_index + 1],
                    right_column[right_index + 1],
                    right_column[right_index],
                )
            )
            left_index += 1
            right_index += 1
        elif next_left < next_right:
            face = _clean_face(
                (
                    left_column[left_index],
                    left_column[left_index + 1],
                    right_column[right_index],
                )
            )
            left_index += 1
        else:
            face = _clean_face(
                (
                    left_column[left_index],
                    right_column[right_index + 1],
                    right_column[right_index],
                )
            )
            right_index += 1

        if len(face) >= 3:
            faces.append(face)
            for edge in zip(face, face[1:] + face[:1], strict=True):
                edges.add(_edge_key(*edge))


def _merge_boundary_extensions(
    patches: Iterable[_LoftedMeshPatch],
    extensions: Iterable[Mesh3],
) -> tuple[Mesh3, ...]:
    patches = tuple(patches)
    meshes = [patch.mesh for patch in patches]
    extension_meshes = tuple(mesh for mesh in extensions if mesh.vertices)
    if meshes and extension_meshes:
        meshes[0] = Mesh3.merged((meshes[0], *extension_meshes))
    return tuple(meshes)


def _keel_boundary_rows(patches: Iterable[_LoftedMeshPatch]) -> tuple[tuple[_Point3, ...], ...]:
    rows: list[tuple[_Point3, ...]] = []
    for patch in patches:
        if patch.group_index == 1:
            rows.extend(patch.nodes)
    return tuple(sorted(rows, key=lambda row: row[0][0]))


def _keel_end_rows(rows: Iterable[tuple[_Point3, ...]]) -> tuple[tuple[_Point3, ...], ...]:
    rows = tuple(rows)
    if len(rows) <= 2:
        return rows
    return (rows[0], rows[-1])


def _keel_end_cap_mesh(rows: Iterable[tuple[_Point3, ...]]) -> Mesh3:
    vertices: list[_Point3] = []
    faces: list[_Face] = []
    edges: set[_Edge] = set()

    for row in rows:
        start = len(vertices)
        vertices.extend((*row, *(_mirror_point(point) for point in reversed(row))))
        face = tuple(range(start, len(vertices)))
        faces.append(face)
        for edge in zip(face, face[1:] + face[:1], strict=True):
            edges.add(_edge_key(*edge))

    return Mesh3(tuple(vertices), tuple(faces), tuple(sorted(edges)))


def _try_close_mesh(mesh: Mesh3, *, tolerance: float) -> Mesh3:
    try:
        return mesh.close_mesh(tolerance=tolerance)
    except ValueError:
        return mesh


def _split_quad_faces(mesh: Mesh3) -> Mesh3:
    edge_counts = _face_edge_counts(mesh.faces)
    faces: list[_Face] = []
    for face in mesh.faces:
        if len(face) == 4:
            split_faces, diagonal = _split_quad(mesh.vertices, face, edge_counts)
            faces.extend(split_faces)
            edge_counts[diagonal] = edge_counts.get(diagonal, 0) + 2
        else:
            faces.append(face)
    return Mesh3(mesh.vertices, tuple(faces), _face_edges(faces))


def _split_quad(
    vertices: tuple[_Point3, ...],
    face: Sequence[int],
    edge_counts: dict[_Edge, int],
) -> tuple[tuple[_Face, _Face], _Edge]:
    a, b, c, d = face
    diagonal_ac_edge = _edge_key(a, c)
    diagonal_bd_edge = _edge_key(b, d)
    if edge_counts.get(diagonal_ac_edge, 0) and not edge_counts.get(diagonal_bd_edge, 0):
        return (((a, b, d), (b, c, d)), diagonal_bd_edge)
    if edge_counts.get(diagonal_bd_edge, 0) and not edge_counts.get(diagonal_ac_edge, 0):
        return (((a, b, c), (a, c, d)), diagonal_ac_edge)

    diagonal_ac = dist(vertices[a], vertices[c])
    diagonal_bd = dist(vertices[b], vertices[d])
    if diagonal_ac <= diagonal_bd:
        return (((a, b, c), (a, c, d)), diagonal_ac_edge)
    return (((a, b, d), (b, c, d)), diagonal_bd_edge)


def _triangulate_mesh_faces(mesh: Mesh3, *, tolerance: float) -> Mesh3:
    output_vertices = list(mesh.vertices)
    output_faces: list[_Face] = []

    for face in mesh.faces:
        if len(face) == 3:
            output_faces.append(face)
            continue
        _extend_triangulated_face(
            mesh.vertices,
            face,
            output_vertices,
            output_faces,
            tolerance=tolerance,
        )

    return Mesh3(tuple(output_vertices), tuple(output_faces), _face_edges(output_faces))


def _extend_triangulated_face(
    vertices: tuple[_Point3, ...],
    face: _Face,
    output_vertices: list[_Point3],
    output_faces: list[_Face],
    *,
    tolerance: float,
) -> None:
    from cady.geometry.plane3 import Plane3
    from cady.operations.triangulate import triangulate

    points = tuple(vertices[index] for index in face)
    plane = Plane3.fit(points)
    nodes = tuple(plane.coordinates(point) for point in points)
    boundary = tuple((index, (index + 1) % len(face)) for index in range(len(face)))
    nodes_out, _edges_out, local_faces = triangulate(
        nodes,
        boundary,
        algorithm="pizza_web",
        tolerance=tolerance,
    )
    if len(local_faces) == 0:
        output_faces.extend(_fan_triangulated_face(face))
        return

    index_map = list(face)
    for index in range(len(face), len(nodes_out)):
        index_map.append(len(output_vertices))
        x, y = nodes_out[index]
        output_vertices.append(plane.point(float(x), float(y)))

    for a, b, c in local_faces:
        output_faces.append((index_map[int(a)], index_map[int(b)], index_map[int(c)]))


def _fan_triangulated_face(face: _Face) -> tuple[_Face, ...]:
    return tuple(
        (int(face[0]), int(face[index]), int(face[index + 1]))
        for index in range(1, len(face) - 1)
    )


def _face_edges(faces: Iterable[Sequence[int]]) -> tuple[_Edge, ...]:
    edges: set[_Edge] = set()
    for face in faces:
        for start, end in zip(face, (*face[1:], face[0]), strict=True):
            edges.add(_edge_key(start, end))
    return tuple(sorted(edges))


def _face_edge_counts(faces: Iterable[Sequence[int]]) -> dict[_Edge, int]:
    counts: dict[_Edge, int] = {}
    for face in faces:
        for start, end in zip(face, (*face[1:], face[0]), strict=True):
            edge = _edge_key(start, end)
            counts[edge] = counts.get(edge, 0) + 1
    return counts


def _node_array(
    polylines: Iterable[Polyline3],
    nodes_on_polyline: int,
    *,
    tolerance: float,
) -> _NodeArray:
    rows: list[tuple[_Point3, ...]] = []
    for polyline in polylines:
        points = _prepared_polyline_points(polyline, tolerance=tolerance)
        lengths = tuple(dist(start, end) for start, end in zip(points, points[1:], strict=False))
        total = sum(lengths)
        if total <= tolerance:
            raise ValueError("each station line must have non-zero length")

        row: list[_Point3] = []
        for node_index in range(nodes_on_polyline):
            target = total * node_index / (nodes_on_polyline - 1)
            row.append(_interpolate_along_points(points, lengths, target))

        nodes = tuple(row)
        x = float(median(point[0] for point in nodes))
        rows.append(tuple((x, point[1], point[2]) for point in nodes))

    if len(rows) < 2:
        raise ValueError("linesplan mesh requires at least two station lines")
    return tuple(rows)


def _node_array_for_spacing(
    polylines: Iterable[Polyline3],
    *,
    node_spacing: float,
    tolerance: float,
) -> _NodeArray:
    polylines = tuple(polylines)
    nodes_on_polyline = _nodes_on_median_polyline_length(polylines, node_spacing=node_spacing)
    return _node_array(polylines, nodes_on_polyline, tolerance=tolerance)


def _nodes_on_median_polyline_length(
    polylines: Sequence[Polyline3],
    *,
    node_spacing: float,
) -> int:
    if not polylines:
        raise ValueError("station polyline group requires at least one polyline")
    median_length = float(median(polyline.length for polyline in polylines))
    return max(2, round(median_length / node_spacing) + 1)


def _mesh_node_array(nodes: _NodeArray) -> Mesh3:
    width = len(nodes[0])
    vertices = tuple(point for row in nodes for point in row)
    edges: set[_Edge] = set()
    faces: list[_Face] = []

    for row_index in range(len(nodes)):
        start = row_index * width
        for column_index in range(width - 1):
            edges.add((start + column_index, start + column_index + 1))

    for row_index in range(len(nodes) - 1):
        start = row_index * width
        next_start = (row_index + 1) * width
        for column_index in range(width):
            edges.add((start + column_index, start + width + column_index))
        for column_index in range(width - 1):
            faces.append(
                (
                    start + column_index,
                    next_start + column_index,
                    next_start + column_index + 1,
                    start + column_index + 1,
                )
            )

    return Mesh3(vertices, tuple(faces), tuple(sorted(edges)))


def _prepared_polyline_points(polyline: Polyline3, *, tolerance: float) -> tuple[_Point3, ...]:
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
    return points


def _interpolate_along_points(
    points: tuple[_Point3, ...],
    lengths: tuple[float, ...],
    target: float,
) -> _Point3:
    walked = 0.0
    for start, end, length in zip(points, points[1:], lengths, strict=True):
        next_walked = walked + length
        if target <= next_walked or end == points[-1]:
            ratio = 0.0 if length == 0.0 else (target - walked) / length
            return (
                start[0] + (end[0] - start[0]) * ratio,
                start[1] + (end[1] - start[1]) * ratio,
                start[2] + (end[2] - start[2]) * ratio,
            )
        walked = next_walked
    return points[-1]


def _grid_edges(row_count: int, width: int) -> tuple[_Edge, ...]:
    edges: set[_Edge] = set()
    for row_index in range(row_count):
        start = row_index * width
        for column_index in range(width - 1):
            edges.add((start + column_index, start + column_index + 1))

    for row_index in range(row_count - 1):
        start = row_index * width
        next_start = (row_index + 1) * width
        for column_index in range(width):
            edges.add((start + column_index, next_start + column_index))

    return tuple(sorted(edges))


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
        unique: list[int] = []
        for index in mapped:
            if index not in unique:
                unique.append(index)
        if len(unique) >= 3:
            welded_faces.append(tuple(unique))

    welded_edges: set[_Edge] = set()
    for a, b in mesh.edges:
        start, end = remap[a], remap[b]
        if start != end:
            welded_edges.add(_edge_key(start, end))

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


def _polyline_length(points: tuple[_Point3, ...]) -> float:
    return sum(dist(start, end) for start, end in zip(points, points[1:], strict=False))


def _matches_any_point(
    point: _Point3,
    targets: Iterable[_Point3],
    *,
    tolerance: float,
) -> bool:
    return any(dist(point, target) <= tolerance for target in targets)


def _edge_key(start: int, end: int) -> _Edge:
    return (min(start, end), max(start, end))


def _mirror_point(point: _Point3) -> _Point3:
    return (point[0], -point[1], point[2])


def _clean_face(indices: Iterable[int]) -> _Face:
    face: list[int] = []
    for index in indices:
        if not face or face[-1] != index:
            face.append(index)
    if len(face) > 1 and face[0] == face[-1]:
        face.pop()
    return tuple(face)


def _resolve_node_spacing(
    polylines: Iterable[Polyline3],
    node_spacing: float | None,
    nodes_on_polyline: int | None,
    nodes_per_station: int | None,
    *,
    default: float,
) -> float:
    has_node_count = nodes_on_polyline is not None or nodes_per_station is not None
    if node_spacing is not None and has_node_count:
        raise ValueError("use node_spacing or a node count, not both")
    if node_spacing is not None:
        return _validate_tolerance(node_spacing, "node_spacing")
    if nodes_on_polyline is not None or nodes_per_station is not None:
        count = _resolve_nodes_on_polyline(nodes_on_polyline, nodes_per_station, default=0)
        return _node_spacing_for_count(tuple(polylines), count)
    return _validate_tolerance(default, "node_spacing")


def _node_spacing_for_count(polylines: Sequence[Polyline3], count: int) -> float:
    if not polylines:
        raise ValueError("station_lines must not be empty")
    return float(median(polyline.length for polyline in polylines)) / (count - 1)


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


def _validate_tolerance(tolerance: float, name: str) -> float:
    if tolerance <= 0.0 or not isfinite(tolerance):
        raise ValueError(f"{name} must be positive")
    return float(tolerance)


def _validate_ratio(value: float, name: str) -> float:
    value = float(value)
    if value < 0.0 or value > 1.0 or not isfinite(value):
        raise ValueError(f"{name} must be between 0 and 1")
    return value


__all__ = ["Linesplan", "LinesplanMeshSettings"]
