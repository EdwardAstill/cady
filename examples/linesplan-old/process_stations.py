"""Clean, connect, orient, and split station polylines.

The linesplan DXF contains station geometry as many curve fragments. This
process turns those fragments into station rows that are consistent enough to
loft: duplicate points are removed, near-zero centreline offsets are snapped to
zero, fragments are connected, station polylines are oriented top-to-bottom,
and the oriented rows are converted to points before the top region is split at
the keel discontinuity.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from math import dist
from statistics import median
from typing import TypeAlias, cast

from cady import Polyline3

Point3: TypeAlias = tuple[float, float, float]

TOLERANCE = 1e-3
SNAP_TOLERANCE = 1000.0
MIN_STATION_FRAGMENT_LENGTH = 1.0
KEEL_DISCONTINUITY_ANGLE_DEGREES = 60.0


@dataclass(frozen=True, slots=True)
class ProcessedStations:
    """Station rows and the derived points used by later mesh processes."""

    connected_lines: tuple[Polyline3, ...]
    prepared_lines: tuple[Polyline3, ...]
    yellow_top_lines: tuple[Polyline3, ...]
    red_top_lines: tuple[Polyline3, ...]
    top_positive_y_points: tuple[Point3, ...]
    top_discontinuity_points: tuple[Point3, ...]
    station_end_points: tuple[Point3, ...]


def process_stations(polylines: Iterable[Polyline3]) -> ProcessedStations:
    """Run the complete station cleanup process."""
    connected = connect_station_fragments(polylines, SNAP_TOLERANCE)
    oriented = orient_station_lines(connected)
    prepared = prepare_station_lines(oriented)
    yellow_top_lines, red_top_lines = split_station_lines(prepared)
    return ProcessedStations(
        connected_lines=connected,
        prepared_lines=prepared,
        yellow_top_lines=yellow_top_lines,
        red_top_lines=red_top_lines,
        top_positive_y_points=station_top_positive_y_points(prepared),
        top_discontinuity_points=station_top_discontinuity_points(prepared),
        station_end_points=station_end_points(prepared),
    )


def connect_station_fragments(
    polylines: Iterable[Polyline3],
    snap_tolerance: float,
) -> tuple[Polyline3, ...]:
    """Join station fragments whose endpoints or endpoint-to-segment snaps match."""
    rows: list[tuple[Point3, ...]] = []
    for polyline in polylines:
        row = _dedupe(_clean_point(point) for point in polyline.to_array(tolerance=TOLERANCE))
        if _polyline_length(row) > MIN_STATION_FRAGMENT_LENGTH:
            rows.append(row)

    connected: list[tuple[Point3, ...]] = []

    while rows:
        row = rows.pop(0)
        while True:
            match_index = None
            match_row: tuple[Point3, ...] | None = None

            for index, candidate in enumerate(rows):
                # Drop exact duplicate fragments before trying to join geometry.
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

                # Some station fragments terminate near the middle of another
                # fragment. Insert the snapped endpoint into the target row so
                # the final connected station keeps that geometric detail.
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


def prepare_station_lines(polylines: Iterable[Polyline3]) -> tuple[Polyline3, ...]:
    """Convert oriented station lines to cleaned, trimmed point rows."""
    return tuple(_prepare_station_line(polyline) for polyline in polylines)


def orient_station_lines(polylines: Iterable[Polyline3]) -> tuple[Polyline3, ...]:
    """Orient connected station polylines for consistent lofting."""
    return tuple(_orient_station_line(polyline) for polyline in polylines)


def split_station_lines(
    polylines: Iterable[Polyline3],
) -> tuple[tuple[Polyline3, ...], tuple[Polyline3, ...]]:
    """Split station lines into the yellow positive-y top and red keel top groups."""
    positive_y_top: list[Polyline3] = []
    discontinuity_top: list[Polyline3] = []

    for polyline in polylines:
        points = _dedupe(_clean_point(point) for point in polyline.to_array(tolerance=TOLERANCE))
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


def station_top_positive_y_points(polylines: Iterable[Polyline3]) -> tuple[Point3, ...]:
    """Return the highest positive-y point on each prepared station line."""
    points: list[Point3] = []
    for polyline in polylines:
        polyline_points = tuple(
            _clean_point(point) for point in polyline.to_array(tolerance=TOLERANCE)
        )
        positive_y_points = tuple(point for point in polyline_points if point[1] > TOLERANCE)
        if positive_y_points:
            points.append(max(positive_y_points, key=lambda point: point[2]))
    return tuple(points)


def station_top_discontinuity_points(polylines: Iterable[Polyline3]) -> tuple[Point3, ...]:
    """Return the highest keel discontinuity detected on each prepared station line."""
    points: list[Point3] = []
    for polyline in polylines:
        discontinuities = tuple(
            _clean_point(point)
            for point in polyline.discontinuities(
                min_angle_degrees=KEEL_DISCONTINUITY_ANGLE_DEGREES,
                min_segment_length=TOLERANCE,
            )
        )
        if discontinuities:
            points.append(max(discontinuities, key=lambda point: point[2]))
    return tuple(points)


def station_end_points(polylines: Iterable[Polyline3]) -> tuple[Point3, ...]:
    """Return cleaned end points for the prepared station lines."""
    return tuple(_clean_point(polyline.end) for polyline in polylines)


def _dedupe(points: Iterable[Point3]) -> tuple[Point3, ...]:
    kept: list[Point3] = []
    for point in points:
        if not kept or dist(point, kept[-1]) > TOLERANCE:
            kept.append(point)
    return tuple(kept)


def _polyline_length(points: tuple[Point3, ...]) -> float:
    return sum(dist(start, end) for start, end in zip(points, points[1:], strict=False))


def _prepare_station_line(polyline: Polyline3) -> Polyline3:
    points = _dedupe(_clean_point(point) for point in polyline.to_array(tolerance=TOLERANCE))
    points = _trim_after_top_positive_y(points)
    return Polyline3(points)


def _orient_station_line(polyline: Polyline3) -> Polyline3:
    if polyline.end[2] > polyline.start[2]:
        return polyline.reverse()
    return polyline


def _top_discontinuity_index(points: tuple[Point3, ...]) -> int | None:
    discontinuities = Polyline3(points).discontinuities(
        min_angle_degrees=KEEL_DISCONTINUITY_ANGLE_DEGREES,
        min_segment_length=TOLERANCE,
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
        if distance <= TOLERANCE:
            discontinuity_indices.append(index)

    if not discontinuity_indices:
        return None
    return max(discontinuity_indices, key=lambda index: points[index][2])


def _trim_after_top_positive_y(points: tuple[Point3, ...]) -> tuple[Point3, ...]:
    top_index = _top_positive_y_index(points)
    # Bow stations can start on the centreline and then step outboard; that
    # first outboard point is part of the contour, not a trim boundary.
    if top_index is None or top_index <= 1 or top_index == len(points) - 1:
        return points
    return points[: top_index + 1]


def _top_positive_y_index(points: tuple[Point3, ...]) -> int | None:
    positive_y_points = (
        (index, point) for index, point in enumerate(points) if point[1] > TOLERANCE
    )
    top = max(positive_y_points, key=lambda item: item[1][2], default=None)
    if top is None:
        return None
    return top[0]


def _clean_point(point: object) -> Point3:
    coordinates = cast(Sequence[float], point)
    x, y, z = (float(coordinates[0]), float(coordinates[1]), float(coordinates[2]))
    if abs(y) <= TOLERANCE:
        y = 0.0
    return (x, y, z)
