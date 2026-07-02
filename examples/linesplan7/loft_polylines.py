"""Loft processed station polylines into a simple mesh grid."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from math import dist
from statistics import median
from typing import TypeAlias, cast

from cady import Mesh3, Polyline3

Point3: TypeAlias = tuple[float, float, float]
NodeArray: TypeAlias = tuple[tuple[Point3, ...], ...]

TARGET_NODE_SPACING = 400.0
TOLERANCE = 1e-3


def loft_polylines(
    polylines: Iterable[Polyline3],
    node_spacing: float = TARGET_NODE_SPACING,
) -> Mesh3:
    nodes = get_node_array(polylines, node_spacing=node_spacing)
    return mesh_node_array(nodes)


def get_node_array(
    polylines: Iterable[Polyline3],
    *,
    node_spacing: float = TARGET_NODE_SPACING,
) -> NodeArray:
    polylines = tuple(polylines)
    nodes_on_polyline = nodes_on_median_polyline_length(polylines, node_spacing=node_spacing)
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

        nodes = tuple(row)
        x = float(median(point[0] for point in nodes))
        rows.append(tuple((x, point[1], point[2]) for point in nodes))

    return tuple(rows)


def nodes_on_median_polyline_length(
    polylines: Sequence[Polyline3],
    *,
    node_spacing: float = TARGET_NODE_SPACING,
) -> int:
    if not polylines:
        raise ValueError("get_node_array requires at least one polyline")

    median_length = float(median(polyline.length for polyline in polylines))
    return max(2, round(median_length / node_spacing) + 1)


def mesh_node_array(nodes: NodeArray) -> Mesh3:
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


def _dedupe(points: Iterable[Point3]) -> tuple[Point3, ...]:
    kept: list[Point3] = []
    for point in points:
        if not kept or dist(point, kept[-1]) > TOLERANCE:
            kept.append(point)
    return tuple(kept)


def _point3(point: object) -> Point3:
    coordinates = cast(Sequence[float], point)
    return (float(coordinates[0]), float(coordinates[1]), float(coordinates[2]))


if __name__ == "__main__":
    raise SystemExit("Run main.py to process, loft, mirror, and view the linesplan mesh.")
