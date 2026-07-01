"""Source wireframe object for the testing examples.

Change the three source arcs here when experimenting with the strip-mesh
example. ``testing5-strip-mesh.py`` imports these rows directly.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import cos, pi, sin, sqrt
from typing import NamedTuple

from cady import Polyline3, Wireframe3


class Point3(NamedTuple):
    x: float
    y: float
    z: float

    def tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


PointLike3 = tuple[float, float, float] | Point3
EdgeIndex = tuple[int, int]

RADIUS = 5.0
SAMPLES = 33
INTERSECTION_TOLERANCE = 1e-9
DIAGONAL_SCALE = 1.0 / sqrt(2.0)


@dataclass(frozen=True)
class WireframeObject:
    radius: float
    linesplan: tuple[Polyline3, ...]
    wireframe: Wireframe3


def quarter_sphere_linesplan(*, radius: float, samples: int) -> tuple[Polyline3, ...]:
    if radius <= 0.0:
        raise ValueError("radius must be positive")
    if samples < 3:
        raise ValueError("samples must be at least 3")

    sample_offsets = semicircle_sample_offsets(radius=radius, samples=samples)
    linesplan = (
        Polyline3(tuple((side, y, 0.0) for side, y in sample_offsets)),
        Polyline3(
            tuple(
                (side * DIAGONAL_SCALE, y, -side * DIAGONAL_SCALE)
                for side, y in sample_offsets
            )
        ),
        Polyline3(tuple((0.0, y, -side) for side, y in sample_offsets)),
    )
    validate_matching_y_bounds(linesplan)
    return linesplan


def semicircle_sample_offsets(
    *,
    radius: float,
    samples: int,
) -> tuple[tuple[float, float], ...]:
    offsets: list[tuple[float, float]] = [(0.0, -radius)]

    for index in range(1, samples - 1):
        theta = -pi / 2.0 + pi * index / (samples - 1)
        offsets.append((radius * cos(theta), radius * sin(theta)))

    offsets.append((0.0, radius))
    return tuple(offsets)


def validate_matching_y_bounds(
    polylines: Iterable[Polyline3],
    *,
    tolerance: float = INTERSECTION_TOLERANCE,
) -> None:
    require_positive_tolerance(tolerance)

    linesplan = tuple(polylines)
    if not linesplan:
        raise ValueError("linesplan must contain at least one polyline")

    expected_min, expected_max = polyline_y_bounds(linesplan[0])
    for index, polyline in enumerate(linesplan[1:], start=2):
        actual_min, actual_max = polyline_y_bounds(polyline)
        if (
            abs(actual_min - expected_min) > tolerance
            or abs(actual_max - expected_max) > tolerance
        ):
            raise ValueError(
                "all linesplan polylines must have the same y bounds; "
                f"polyline_1=({expected_min:g}, {expected_max:g}), "
                f"polyline_{index}=({actual_min:g}, {actual_max:g})"
            )


def polyline_y_bounds(polyline: Polyline3) -> tuple[float, float]:
    if not polyline.vertices:
        raise ValueError("linesplan polylines must contain at least one vertex")

    y_values = [vertex[1] for vertex in polyline.vertices]
    return min(y_values), max(y_values)


def wireframe_from_polylines(polylines: Iterable[Polyline3]) -> Wireframe3:
    vertices: list[Point3] = []
    vertex_indices: dict[tuple[float, float, float], int] = {}
    edges: list[EdgeIndex] = []

    for polyline in polylines:
        previous_index: int | None = None
        for vertex in polyline.vertices:
            current_index = index_point(vertices, vertex_indices, vertex)
            if previous_index is not None and previous_index != current_index:
                append_unique_edge(edges, (previous_index, current_index))
            previous_index = current_index

    return Wireframe3(tuple(vertices), tuple(edges))


def index_point(
    vertices: list[Point3],
    vertex_indices: dict[tuple[float, float, float], int],
    point: PointLike3,
) -> int:
    value = as_point3(point)
    key = value.tuple()
    existing_index = vertex_indices.get(key)
    if existing_index is not None:
        return existing_index

    new_index = len(vertices)
    vertex_indices[key] = new_index
    vertices.append(value)
    return new_index


def append_unique_edge(edges: list[EdgeIndex], edge: EdgeIndex) -> None:
    if edge[0] == edge[1]:
        return

    key = edge_key(edge)
    if any(edge_key(existing) == key for existing in edges):
        return
    edges.append(edge)


def edge_key(edge: EdgeIndex) -> EdgeIndex:
    start, end = edge
    return (start, end) if start < end else (end, start)


def require_positive_tolerance(tolerance: float) -> None:
    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive")


def as_point3(point: PointLike3) -> Point3:
    if isinstance(point, Point3):
        return point
    return Point3(*point)


def build_wireframe_object(*, radius: float, samples: int) -> WireframeObject:
    linesplan = quarter_sphere_linesplan(radius=radius, samples=samples)
    return WireframeObject(
        radius=radius,
        linesplan=linesplan,
        wireframe=wireframe_from_polylines(linesplan),
    )


WIREFRAME_OBJECT = build_wireframe_object(radius=RADIUS, samples=SAMPLES)
