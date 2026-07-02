"""Loft prepared station groups into mesh patches.

The station processor produces two ordered groups of polylines. This module
resamples each station in a group to a common node count, builds quad mesh
patches from those node rows, and records the boundary nodes that the closing
process needs to extend the half hull to the centreline.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from math import dist
from statistics import median
from typing import TypeAlias, cast

from cady import Mesh3, Polyline3

Point3: TypeAlias = tuple[float, float, float]
PolylineGroup: TypeAlias = tuple[Polyline3, ...]
NodeArray: TypeAlias = tuple[tuple[Point3, ...], ...]

TARGET_NODE_SPACING = 400.0
TOLERANCE = 1e-3


@dataclass(frozen=True, slots=True)
class BoundaryNode:
    """A mesh node that belongs to a centreline-closing boundary chain."""

    row_index: int
    point: Point3


@dataclass(frozen=True, slots=True)
class LoftedPatch:
    """A lofted mesh patch plus the source rows used to build it."""

    group_index: int
    polylines: PolylineGroup
    nodes: NodeArray
    mesh: Mesh3
    yellow_nodes: tuple[BoundaryNode, ...] = ()
    green_nodes: tuple[BoundaryNode, ...] = ()


def loft_station_groups(
    polyline_groups: Iterable[PolylineGroup],
    station_end_points: Iterable[Point3],
) -> tuple[LoftedPatch, ...]:
    """Loft every non-empty station group and mark its closing boundaries."""
    patches = tuple(
        patch
        for group_index, polyline_group in enumerate(polyline_groups)
        if polyline_group
        for patch in (_loft_polyline_group(group_index, polyline_group),)
    )
    return tuple(_mark_boundary_nodes(patch, station_end_points) for patch in patches)


def node_array_from_polylines(polylines: Iterable[Polyline3]) -> NodeArray:
    """Resample every polyline to the median station node count."""
    polylines = tuple(polylines)
    nodes_on_polyline = nodes_on_median_polyline_length(polylines)
    rows: list[tuple[Point3, ...]] = []
    for polyline in polylines:
        points = _dedupe(_point3(point) for point in polyline.to_array(tolerance=TOLERANCE))
        lengths = tuple(dist(start, end) for start, end in zip(points, points[1:], strict=False))
        total = sum(lengths)

        row: list[Point3] = []
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

        # A station should sit on a single x-plane; using the row median removes
        # tiny DXF noise without changing the station ordering.
        nodes = tuple(row)
        x = float(median(point[0] for point in nodes))
        rows.append(tuple((x, point[1], point[2]) for point in nodes))

    return tuple(rows)


def nodes_on_median_polyline_length(polylines: Sequence[Polyline3]) -> int:
    """Choose a shared node count from the median station length."""
    if not polylines:
        raise ValueError("node_array_from_polylines requires at least one polyline")

    median_length = float(median(polyline.length for polyline in polylines))
    return max(2, round(median_length / TARGET_NODE_SPACING) + 1)


def mesh_node_array(nodes: NodeArray) -> Mesh3:
    """Build a quad mesh grid from station node rows."""
    width = len(nodes[0])
    vertices = tuple(point for row in nodes for point in row)
    edges: set[tuple[int, int]] = set()
    faces: list[tuple[int, ...]] = []

    for row_index in range(len(nodes)):
        start = row_index * width
        for column_index in range(width - 1):
            edges.add((start + column_index, start + column_index + 1))

    for row_index in range(len(nodes) - 1):
        start = row_index * width
        next_start = (row_index + 1) * width
        for column_index in range(width):
            edges.add((start + column_index, next_start + column_index))
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


def _loft_polyline_group(group_index: int, polylines: PolylineGroup) -> LoftedPatch:
    nodes = node_array_from_polylines(polylines)
    return LoftedPatch(
        group_index=group_index,
        polylines=polylines,
        nodes=nodes,
        mesh=mesh_node_array(nodes),
    )


def _mark_boundary_nodes(
    patch: LoftedPatch,
    station_end_points: Iterable[Point3],
) -> LoftedPatch:
    station_end_points = tuple(station_end_points)
    end_column = len(patch.nodes[0]) - 1
    yellow_nodes: tuple[BoundaryNode, ...] = ()
    if patch.group_index == 0:
        yellow_nodes = tuple(
            BoundaryNode(row_index, row[0]) for row_index, row in enumerate(patch.nodes)
        )

    green_nodes = tuple(
        BoundaryNode(row_index, patch.nodes[row_index][end_column])
        for row_index, polyline in enumerate(patch.polylines)
        if _matches_any_point(polyline.end, station_end_points)
    )
    return LoftedPatch(
        group_index=patch.group_index,
        polylines=patch.polylines,
        nodes=patch.nodes,
        mesh=patch.mesh,
        yellow_nodes=yellow_nodes,
        green_nodes=green_nodes,
    )


def _matches_any_point(point: Point3, targets: Iterable[Point3]) -> bool:
    return any(dist(point, target) <= TOLERANCE for target in targets)


def _dedupe(points: Iterable[Point3]) -> tuple[Point3, ...]:
    kept: list[Point3] = []
    for point in points:
        if not kept or dist(point, kept[-1]) > TOLERANCE:
            kept.append(point)
    return tuple(kept)


def _point3(point: object) -> Point3:
    coordinates = cast(Sequence[float], point)
    return (float(coordinates[0]), float(coordinates[1]), float(coordinates[2]))
