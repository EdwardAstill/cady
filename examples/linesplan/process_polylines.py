"""Clean, join, split, and inspect station polylines."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from colorsys import hsv_to_rgb
from math import dist
from statistics import median
from typing import TypeAlias, cast

from cady import DisplayStyle, PointCloud3, Polyline3, Scene, Wireframe3

Point3: TypeAlias = tuple[float, float, float]
PolylineGroup: TypeAlias = tuple[Polyline3, ...]
ProcessedPolylineGroups: TypeAlias = tuple[PolylineGroup, PolylineGroup]

STATION_GEOMETRY_TOLERANCE = 1e-3
DXF_SNAP_TOLERANCE = 1000.0
MIN_STATION_FRAGMENT_LENGTH = 1.0
KEEL_DISCONTINUITY_ANGLE_DEGREES = 60.0
TOP_POSITIVE_Y_STYLE = DisplayStyle(color=(1.0, 0.95, 0.05), point_size=10.0)
DISCONTINUITY_STYLE = DisplayStyle(color=(1.0, 0.18, 0.05), point_size=12.0)
END_POINT_STYLE = DisplayStyle(color=(0.1, 0.82, 0.24), point_size=10.0)
SOURCE_STATION_STYLE = DisplayStyle(color=(0.05, 0.23, 0.55), render_mode="wireframe")


def process_polylines(polylines: Iterable[Polyline3]) -> ProcessedPolylineGroups:
    station_lines = process_station_lines(polylines, DXF_SNAP_TOLERANCE)
    station_lines = prepare_station_lines(station_lines)
    return split_station_lines(station_lines)


def prepare_station_lines(polylines: Iterable[Polyline3]) -> tuple[Polyline3, ...]:
    return tuple(_prepare_station_line(polyline) for polyline in polylines)


def split_station_lines(polylines: Iterable[Polyline3]) -> ProcessedPolylineGroups:
    positive_y_top: list[Polyline3] = []
    discontinuity_top: list[Polyline3] = []

    for polyline in polylines:
        points = _dedupe(
            _clean_point(point)
            for point in polyline.to_array(tolerance=STATION_GEOMETRY_TOLERANCE)
        )
        discontinuity_index = _top_discontinuity_index(points)
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


def process_station_lines(
    polylines: Iterable[Polyline3],
    snap_tolerance: float,
) -> tuple[Polyline3, ...]:
    rows: list[tuple[Point3, ...]] = []
    for polyline in polylines:
        row = _dedupe(
            _clean_point(point)
            for point in polyline.to_array(tolerance=STATION_GEOMETRY_TOLERANCE)
        )
        if _polyline_length(row) > MIN_STATION_FRAGMENT_LENGTH:
            rows.append(row)

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
                    if (
                        same <= STATION_GEOMETRY_TOLERANCE
                        or flipped <= STATION_GEOMETRY_TOLERANCE
                    ):
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


def station_top_positive_y_points(polylines: Iterable[Polyline3]) -> tuple[Point3, ...]:
    points: list[Point3] = []
    for polyline in polylines:
        polyline_points = tuple(
            _clean_point(point)
            for point in polyline.to_array(tolerance=STATION_GEOMETRY_TOLERANCE)
        )
        positive_y_points = tuple(
            point for point in polyline_points if point[1] > STATION_GEOMETRY_TOLERANCE
        )
        if positive_y_points:
            points.append(max(positive_y_points, key=lambda point: point[2]))
    return tuple(points)


def station_top_discontinuity_points(polylines: Iterable[Polyline3]) -> tuple[Point3, ...]:
    points: list[Point3] = []
    for polyline in polylines:
        discontinuities = tuple(
            _clean_point(point)
            for point in polyline.discontinuities(
                min_angle_degrees=KEEL_DISCONTINUITY_ANGLE_DEGREES,
                min_segment_length=STATION_GEOMETRY_TOLERANCE,
            )
        )
        if discontinuities:
            points.append(max(discontinuities, key=lambda point: point[2]))
    return tuple(points)


def station_end_points(polylines: Iterable[Polyline3]) -> tuple[Point3, ...]:
    return tuple(_clean_point(polyline.end) for polyline in polylines)


def view_processed_station_lines(
    polylines: Iterable[Polyline3],
    top_positive_y_points: Iterable[Point3] = (),
    top_discontinuities: Iterable[Point3] = (),
    end_points: Iterable[Point3] = (),
) -> None:
    polylines = tuple(polylines)
    scene = Scene(name="processed_station_polylines")
    for index, polyline in enumerate(polylines):
        scene = scene.add(
            polyline.points(),
            name=f"station_{index:02d}",
            style=DisplayStyle(color=hsv_to_rgb(index / max(len(polylines), 1), 0.72, 0.92)),
        )

    positive_y_points = tuple(top_positive_y_points)
    if positive_y_points:
        scene = scene.add(
            PointCloud3(positive_y_points),
            name="station_top_positive_y_points",
            style=TOP_POSITIVE_Y_STYLE,
        )

    discontinuities = tuple(top_discontinuities)
    if discontinuities:
        scene = scene.add(
            PointCloud3(discontinuities),
            name="station_top_discontinuities",
            style=DISCONTINUITY_STYLE,
        )

    ends = tuple(end_points)
    if ends:
        scene = scene.add(
            PointCloud3(ends),
            name="station_end_points",
            style=END_POINT_STYLE,
        )
    scene.view(title="processed station polylines")


def view_original_station_lines(polylines: Iterable[Polyline3]) -> None:
    wireframe = Wireframe3.from_polylines(polylines)
    wireframe.view(title="original station polylines", style=SOURCE_STATION_STYLE)


def _dedupe(points: Iterable[Point3]) -> tuple[Point3, ...]:
    kept: list[Point3] = []
    for point in points:
        if not kept or dist(point, kept[-1]) > STATION_GEOMETRY_TOLERANCE:
            kept.append(point)
    return tuple(kept)


def _polyline_length(points: tuple[Point3, ...]) -> float:
    return sum(dist(start, end) for start, end in zip(points, points[1:], strict=False))


def _prepare_station_line(polyline: Polyline3) -> Polyline3:
    points = _dedupe(
        _clean_point(point)
        for point in polyline.to_array(tolerance=STATION_GEOMETRY_TOLERANCE)
    )
    points = _trim_after_top_positive_y(points)
    prepared = Polyline3(points)
    if prepared.end[2] > prepared.start[2]:
        prepared = prepared.reverse()
    return prepared


def _top_discontinuity_index(points: tuple[Point3, ...]) -> int | None:
    discontinuities = Polyline3(points).discontinuities(
        min_angle_degrees=KEEL_DISCONTINUITY_ANGLE_DEGREES,
        min_segment_length=STATION_GEOMETRY_TOLERANCE,
    )
    if not discontinuities:
        return None

    discontinuity_indices: list[int] = []
    for discontinuity in discontinuities:
        point = _clean_point(discontinuity)
        index, distance = min(
            ((index, dist(candidate, point)) for index, candidate in enumerate(points)),
            key=lambda item: item[1],
        )
        if distance <= STATION_GEOMETRY_TOLERANCE:
            discontinuity_indices.append(index)

    if not discontinuity_indices:
        return None
    return max(discontinuity_indices, key=lambda index: points[index][2])


def _trim_after_top_positive_y(points: tuple[Point3, ...]) -> tuple[Point3, ...]:
    top_index = _top_positive_y_index(points)
    if top_index is None or top_index == 0 or top_index == len(points) - 1:
        return points
    return points[: top_index + 1]


def _top_positive_y_index(points: tuple[Point3, ...]) -> int | None:
    positive_y_points = (
        (index, point)
        for index, point in enumerate(points)
        if point[1] > STATION_GEOMETRY_TOLERANCE
    )
    top = max(positive_y_points, key=lambda item: item[1][2], default=None)
    if top is None:
        return None
    return top[0]


def _clean_point(point: object) -> Point3:
    coordinates = cast(Sequence[float], point)
    x, y, z = (float(coordinates[0]), float(coordinates[1]), float(coordinates[2]))
    if abs(y) <= STATION_GEOMETRY_TOLERANCE:
        y = 0.0
    return (x, y, z)


if __name__ == "__main__":
    from wireframe import STATION_POLYLINES

    processed_station_polylines = prepare_station_lines(
        process_station_lines(STATION_POLYLINES, DXF_SNAP_TOLERANCE)
    )
    view_original_station_lines(STATION_POLYLINES)
    view_processed_station_lines(
        processed_station_polylines,
        station_top_positive_y_points(processed_station_polylines),
        station_top_discontinuity_points(processed_station_polylines),
        station_end_points(processed_station_polylines),
    )
