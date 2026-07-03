"""Lofting helpers for closed and sectioned 3D curves."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from math import dist
from typing import TypeAlias, cast

Point3: TypeAlias = tuple[float, float, float]
Face: TypeAlias = tuple[int, int, int]
Edge: TypeAlias = tuple[int, int]


@dataclass(frozen=True, slots=True)
class LoftMesh:
    """Simple loft result containing vertices, faces, and sampled edges."""

    vertices: tuple[Point3, ...]
    faces: tuple[Face, ...]
    edges: tuple[Edge, ...]


def loft_closed_curves3(
    start_curve: object,
    end_curve: object,
    *,
    tolerance: float,
):
    """Loft between two closed 3D curves and return a ``Mesh3``."""
    start = _curve_points(start_curve, tolerance=tolerance)
    end = _curve_points(end_curve, tolerance=tolerance)
    return loft_closed_loops3(start, end, tolerance=tolerance)


def loft_closed_loops3(
    start: Sequence[Point3],
    end: Sequence[Point3],
    *,
    tolerance: float,
):
    """Loft between two closed loops and return a ``Mesh3``."""
    from cady.geometry.mesh import Mesh3

    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive")
    start_loop = _dedupe_closed3(tuple(start))
    end_loop = _dedupe_closed3(tuple(end))
    if len(start_loop) < 3 or len(end_loop) < 3:
        raise ValueError("loft loops must contain at least three points")

    sample_count = max(len(start_loop), len(end_loop))
    start_row = _resample_closed_loop(start_loop, sample_count)
    end_row = _resample_closed_loop(end_loop, sample_count)
    vertices = start_row + end_row
    faces: list[Face] = []
    edges: set[Edge] = set()
    for index in range(sample_count):
        next_index = (index + 1) % sample_count
        a = index
        b = next_index
        c = sample_count + next_index
        d = sample_count + index
        _append_face_if_valid(faces, vertices, (a, b, c), tolerance)
        _append_face_if_valid(faces, vertices, (a, c, d), tolerance)
        edges.add((a, b))
        edges.add((d, c))
        edges.add((a, d))
    return Mesh3(vertices, tuple(faces), tuple(sorted(edges)))


def loft_section_polylines(
    polylines: Iterable[Sequence[Point3]],
    *,
    tolerance: float,
) -> LoftMesh | None:
    """Loft open section polylines into a coarse strip mesh, if possible."""
    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive")

    sections = _section_curves(polylines, tolerance=tolerance)
    if len(sections) < 2:
        return None

    sample_count = min(max(len(vertices) for _x, vertices in sections), 96)
    if sample_count < 2:
        return None

    rows = tuple(
        _resample_polyline(_orient_section(vertices), sample_count) for _x, vertices in sections
    )
    vertices = tuple(point for row in rows for point in row)
    faces: list[Face] = []
    edges: set[Edge] = set()

    for section_index in range(len(rows)):
        row_start = section_index * sample_count
        for sample_index in range(sample_count - 1):
            edges.add((row_start + sample_index, row_start + sample_index + 1))

    for section_index in range(len(rows) - 1):
        left_start = section_index * sample_count
        right_start = (section_index + 1) * sample_count
        for sample_index in range(sample_count):
            edges.add((left_start + sample_index, right_start + sample_index))
        for sample_index in range(sample_count - 1):
            a = left_start + sample_index
            b = right_start + sample_index
            c = left_start + sample_index + 1
            d = right_start + sample_index + 1
            _append_face_if_valid(faces, vertices, (a, b, d), tolerance)
            _append_face_if_valid(faces, vertices, (a, d, c), tolerance)

    if not faces:
        return None
    return LoftMesh(vertices, tuple(faces), tuple(sorted(edges)))


def _curve_points(curve: object, *, tolerance: float) -> tuple[Point3, ...]:
    if not getattr(curve, "closed", False):
        raise ValueError("loft curves must be closed")
    to_array = getattr(curve, "to_array", None)
    if not callable(to_array):
        raise TypeError("curve must provide to_array(tolerance=...)")
    rows = cast(Iterable[Sequence[float]], to_array(tolerance=tolerance))
    return tuple((float(row[0]), float(row[1]), float(row[2])) for row in rows)


def _dedupe_closed3(points: tuple[Point3, ...]) -> tuple[Point3, ...]:
    if len(points) > 1 and points[0] == points[-1]:
        return points[:-1]
    return points


def _resample_closed_loop(vertices: tuple[Point3, ...], count: int) -> tuple[Point3, ...]:
    return _resample_polyline(vertices + (vertices[0],), count + 1)[:-1]


def _section_curves(
    polylines: Iterable[Sequence[Point3]],
    *,
    tolerance: float,
) -> tuple[tuple[float, tuple[Point3, ...]], ...]:
    x_tolerance = max(tolerance, 1e-3)
    grouped: dict[int, list[tuple[float, tuple[Point3, ...]]]] = {}
    for polyline in polylines:
        vertices = tuple((float(x), float(y), float(z)) for x, y, z in polyline)
        if len(vertices) < 4:
            continue
        xs = [point[0] for point in vertices]
        ys = [point[1] for point in vertices]
        zs = [point[2] for point in vertices]
        if max(xs) - min(xs) > x_tolerance:
            continue
        if max(ys) - min(ys) <= x_tolerance or max(zs) - min(zs) <= x_tolerance:
            continue
        length = _polyline_length(vertices)
        if length <= x_tolerance:
            continue
        x = sum(xs) / len(xs)
        grouped.setdefault(round(x / x_tolerance), []).append((length, vertices))

    sections: list[tuple[float, tuple[Point3, ...]]] = []
    for group in grouped.values():
        _length, vertices = max(group, key=lambda item: item[0])
        x = sum(point[0] for point in vertices) / len(vertices)
        sections.append((x, vertices))
    return tuple(sorted(sections, key=lambda item: item[0]))


def _orient_section(vertices: tuple[Point3, ...]) -> tuple[Point3, ...]:
    if vertices[0][2] > vertices[-1][2]:
        return tuple(reversed(vertices))
    return vertices


def _resample_polyline(vertices: tuple[Point3, ...], count: int) -> tuple[Point3, ...]:
    if count < 2:
        raise ValueError("count must be at least 2")
    distances = [0.0]
    for previous, current in zip(vertices, vertices[1:], strict=False):
        distances.append(distances[-1] + dist(previous, current))
    total = distances[-1]
    if total == 0.0:
        return tuple(vertices[0] for _ in range(count))

    sampled: list[Point3] = []
    segment_index = 0
    for sample_index in range(count):
        target = total * sample_index / (count - 1)
        while segment_index < len(distances) - 2 and distances[segment_index + 1] < target:
            segment_index += 1
        start = vertices[segment_index]
        end = vertices[segment_index + 1]
        start_distance = distances[segment_index]
        segment_length = distances[segment_index + 1] - start_distance
        ratio = 0.0 if segment_length == 0.0 else (target - start_distance) / segment_length
        sampled.append(
            (
                start[0] + (end[0] - start[0]) * ratio,
                start[1] + (end[1] - start[1]) * ratio,
                start[2] + (end[2] - start[2]) * ratio,
            )
        )
    return tuple(sampled)


def _polyline_length(vertices: tuple[Point3, ...]) -> float:
    return sum(
        dist(previous, current) for previous, current in zip(vertices, vertices[1:], strict=False)
    )


def _append_face_if_valid(
    faces: list[Face],
    vertices: tuple[Point3, ...],
    face: Face,
    tolerance: float,
) -> None:
    a, b, c = (vertices[index] for index in face)
    if dist(a, b) <= tolerance or dist(b, c) <= tolerance or dist(c, a) <= tolerance:
        return
    faces.append(face)


__all__ = [
    "LoftMesh",
    "loft_closed_curves3",
    "loft_closed_loops3",
    "loft_section_polylines",
]
