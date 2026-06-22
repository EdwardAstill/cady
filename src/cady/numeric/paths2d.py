from __future__ import annotations

from dataclasses import dataclass
from typing import Self

import numpy as np

from cady.numeric.bounds import bounds2
from cady.numeric.transform import Transform2
from cady.numeric.types import PointArray2
from cady.numeric.validation import as_points2


def _ring_area(points: PointArray2) -> float:
    x_values = points[:, 0]
    y_values = points[:, 1]
    return float(
        0.5
        * np.sum(x_values * np.roll(y_values, -1) - y_values * np.roll(x_values, -1))
    )


def _ring_centroid(points: PointArray2) -> tuple[float, PointArray2]:
    signed_area = _ring_area(points)
    if signed_area == 0.0:
        return 0.0, np.mean(points, axis=0)
    x_values = points[:, 0]
    y_values = points[:, 1]
    next_x = np.roll(x_values, -1)
    next_y = np.roll(y_values, -1)
    cross = x_values * next_y - next_x * y_values
    factor = 1.0 / (6.0 * signed_area)
    centroid = np.array(
        [
            factor * np.sum((x_values + next_x) * cross),
            factor * np.sum((y_values + next_y) * cross),
        ],
        dtype=np.float64,
    )
    return signed_area, centroid


@dataclass(frozen=True, slots=True)
class ArrayPolyline2:
    vertices: PointArray2
    closed: bool = False

    def __post_init__(self) -> None:
        vertices = as_points2(self.vertices, name="vertices")
        if len(vertices) == 0:
            raise ValueError("vertices must contain at least one point")
        object.__setattr__(self, "vertices", vertices)

    def bounds(self) -> tuple[PointArray2, PointArray2]:
        return bounds2(self.vertices, name="vertices")

    def transformed(self, transform: Transform2) -> Self:
        return type(self)(transform.apply_points(self.vertices), closed=self.closed)

    def length(self) -> float:
        if len(self.vertices) < 2:
            return 0.0
        segments = np.diff(self.vertices, axis=0)
        length = float(np.sum(np.linalg.norm(segments, axis=1)))
        if self.closed and len(self.vertices) > 2:
            length += float(np.linalg.norm(self.vertices[0] - self.vertices[-1]))
        return length


@dataclass(frozen=True, slots=True)
class ArrayPolygon2:
    outer: PointArray2
    holes: tuple[PointArray2, ...] = ()

    def __post_init__(self) -> None:
        outer = as_points2(self.outer, name="outer")
        if len(outer) < 3:
            raise ValueError("outer must contain at least three points")
        holes: list[PointArray2] = []
        for index, hole in enumerate(self.holes):
            hole_array = as_points2(hole, name=f"holes[{index}]")
            if len(hole_array) < 3:
                raise ValueError(f"holes[{index}] must contain at least three points")
            holes.append(hole_array)
        object.__setattr__(self, "outer", outer)
        object.__setattr__(self, "holes", tuple(holes))

    def bounds(self) -> tuple[PointArray2, PointArray2]:
        return bounds2(self.outer, name="outer")

    def area(self) -> float:
        area = abs(_ring_area(self.outer))
        for hole in self.holes:
            area -= abs(_ring_area(hole))
        return area

    def centroid(self) -> PointArray2:
        signed_outer_area, outer_centroid = _ring_centroid(self.outer)
        weighted_area = abs(signed_outer_area)
        weighted_centroid = outer_centroid * weighted_area
        for hole in self.holes:
            signed_hole_area, hole_centroid = _ring_centroid(hole)
            hole_area = abs(signed_hole_area)
            weighted_area -= hole_area
            weighted_centroid -= hole_centroid * hole_area
        if weighted_area == 0.0:
            raise ValueError("polygon area must be non-zero")
        return weighted_centroid / weighted_area

    def transformed(self, transform: Transform2) -> Self:
        return type(self)(
            transform.apply_points(self.outer),
            holes=tuple(transform.apply_points(hole) for hole in self.holes),
        )

