"""Loft station polylines and view the resulting mesh."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from colorsys import hsv_to_rgb
from math import dist
from statistics import median
from typing import TypeAlias, cast

from wireframe import STATION_POLYLINES

from cady import DisplayStyle, Mesh3, PointCloud3, Polyline3, Scene

Point3: TypeAlias = tuple[float, float, float]
NodeArray: TypeAlias = tuple[tuple[Point3, ...], ...]

NODES_ON_POLYLINE = 48
TOLERANCE = 1e-3
SNAP_TOLERANCE = 1000.0
START_NODE_STYLE = DisplayStyle(color=(1.0, 0.95, 0.05), point_size=10.0)


def loft_polylines2(polylines: Iterable[Polyline3]) -> Mesh3:
    station_lines = process_station_lines(polylines, SNAP_TOLERANCE)
    mirrored_lines = mirror_station_lines(station_lines)
    nodes = get_node_array(mirrored_lines)
    return mesh_node_array(nodes)


def mirror_station_lines(polylines: Iterable[Polyline3]) -> tuple[Polyline3, ...]:
    mirrored: list[Polyline3] = []
    for polyline in polylines:
        points = [_clean_point(point) for point in polyline.to_array(tolerance=TOLERANCE)]
        if points[-1][2] > points[0][2]:
            points = list(reversed(points))

        mirrored_points = [_clean_point((point[0], -point[1], point[2])) for point in points]
        mirrored_points = list(reversed(mirrored_points))
        if dist(points[-1], mirrored_points[0]) <= TOLERANCE:
            mirrored_points = mirrored_points[1:]

        mirrored.append(Polyline3((*points, *mirrored_points)))
    return tuple(mirrored)


def process_station_lines(
    polylines: Iterable[Polyline3],
    snap_tolerance: float,
) -> tuple[Polyline3, ...]:
    rows: list[tuple[Point3, ...]] = [
        _dedupe(_clean_point(point) for point in polyline.to_array(tolerance=TOLERANCE))
        for polyline in polylines
    ]
    connected: list[tuple[Point3, ...]] = []

    while rows:
        row = rows.pop(0)
        while True:
            match_index = None
            match_row: tuple[Point3, ...] | None = None

            for index, candidate in enumerate(rows):
                if len(row) == len(candidate):
                    same = max(dist(a, b) for a, b in zip(row, candidate, strict=True))
                    flipped = max(dist(a, b) for a, b in zip(row, reversed(candidate), strict=True))
                    if same <= TOLERANCE or flipped <= TOLERANCE:
                        match_index = index
                        match_row = row
                        break

                joins: list[tuple[Point3, ...]] = []
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

                best_snap: tuple[float, tuple[Point3, ...]] | None = None
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

                            snap_point = (
                                start[0] + segment[0] * position,
                                start[1] + segment[1] * position,
                                start[2] + segment[2] * position,
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

            row = _dedupe(match_row)
            del rows[match_index]

        connected.append(row)

    connected.sort(key=lambda line: median(point[0] for point in line))
    return tuple(Polyline3(row) for row in connected)


def get_node_array(polylines: Iterable[Polyline3]) -> NodeArray:
    rows: list[tuple[Point3, ...]] = []
    for polyline in polylines:
        points = _dedupe(
            (float(point[0]), float(point[1]), float(point[2]))
            for point in polyline.to_array(tolerance=TOLERANCE)
        )
        if points[-1][2] > points[0][2]:
            points = tuple(reversed(points))

        lengths = tuple(dist(start, end) for start, end in zip(points, points[1:], strict=False))
        total = sum(lengths)

        row: list[Point3] = []
        for node_index in range(NODES_ON_POLYLINE):
            target = total * node_index / (NODES_ON_POLYLINE - 1)
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


def view_node_array(nodes: NodeArray) -> None:
    scene = Scene(name="processed_station_polylines")
    for index, row in enumerate(nodes):
        scene = scene.add(
            row,
            name=f"station_{index:02d}",
            style=DisplayStyle(color=hsv_to_rgb(index / max(len(nodes), 1), 0.72, 0.92)),
        )

    starts = tuple(row[0] for row in nodes)
    scene.add(PointCloud3(starts), name="station_starts", style=START_NODE_STYLE).view(
        title="processed station polylines"
    )


def _dedupe(points: Iterable[Point3]) -> tuple[Point3, ...]:
    kept: list[Point3] = []
    for point in points:
        if not kept or dist(point, kept[-1]) > TOLERANCE:
            kept.append(point)
    return tuple(kept)


def _clean_point(point: object) -> Point3:
    coordinates = cast(Sequence[float], point)
    x, y, z = (float(coordinates[0]), float(coordinates[1]), float(coordinates[2]))
    if abs(y) <= TOLERANCE:
        y = 0.0
    return (x, y, z)


PROCESSED_STATION_POLYLINES = process_station_lines(STATION_POLYLINES, SNAP_TOLERANCE)
MIRRORED_STATION_POLYLINES = mirror_station_lines(PROCESSED_STATION_POLYLINES)
MIRRORED_STATION_NODES = get_node_array(MIRRORED_STATION_POLYLINES)
MIRRORED_STATION_MESH = mesh_node_array(MIRRORED_STATION_NODES)


if __name__ == "__main__":
    view_node_array(MIRRORED_STATION_NODES)
    MIRRORED_STATION_MESH.view(title="mirrored linesplan station mesh")
