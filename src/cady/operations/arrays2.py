"""Validated 2D array-backed curve and polygon containers."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, sqrt
from typing import Self, cast

import numpy as np

from cady.operations.bounds import bounds2
from cady.operations.transforms import Transform2
from cady.operations.types import PointArray2
from cady.operations.validation import as_points2


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
class ArrayBezierSpline2:
    """Piecewise cubic Bezier spline stored as a validated point array."""

    control_points: PointArray2
    closed: bool = False

    def __post_init__(self) -> None:
        control_points = as_points2(self.control_points, name="control_points")
        if len(control_points) < 4 or (len(control_points) - 1) % 3 != 0:
            raise ValueError("control_points must contain 3n + 1 points with n >= 1")
        object.__setattr__(self, "control_points", control_points)

    @property
    def segment_count(self) -> int:
        return (len(self.control_points) - 1) // 3

    def bounds(self) -> tuple[PointArray2, PointArray2]:
        return bounds2(self.control_points, name="control_points")

    def transformed(self, transform: Transform2) -> ArrayBezierSpline2:
        return type(self)(transform.apply_points(self.control_points), closed=self.closed)

    def sample(
        self,
        *,
        samples: int | None = None,
        tolerance: float | None = None,
    ) -> ArrayPolyline2:
        return sample_bezier_spline2(self, samples=samples, tolerance=tolerance)


def evaluate_bezier_spline2(spline: ArrayBezierSpline2, t_values: object) -> PointArray2:
    """Evaluate a spline at normalised parameters in ``[0, 1]``."""
    parameters = np.array(t_values, dtype=np.float64, copy=True)
    if parameters.ndim != 1:
        raise ValueError("t_values must be a rank 1 array")
    if not np.all(np.isfinite(parameters)):
        raise ValueError("t_values must contain only finite values")
    if np.any((parameters < 0.0) | (parameters > 1.0)):
        raise ValueError("t_values must be between 0 and 1")

    segment_count = spline.segment_count
    scaled = parameters * segment_count
    segment_indices = np.minimum(np.floor(scaled).astype(np.int64), segment_count - 1)
    local_t = scaled - segment_indices
    local_t = np.where(parameters == 1.0, 1.0, local_t)

    result = np.empty((len(parameters), 2), dtype=np.float64)
    for output_index, (segment_index, parameter) in enumerate(
        zip(segment_indices, local_t, strict=True)
    ):
        start = segment_index * 3
        p0, p1, p2, p3 = spline.control_points[start : start + 4]
        inverse = 1.0 - float(parameter)
        result[output_index] = (
            inverse**3 * p0
            + 3.0 * inverse**2 * parameter * p1
            + 3.0 * inverse * parameter**2 * p2
            + parameter**3 * p3
        )
    return cast(PointArray2, result)


def sample_bezier_spline2(
    spline: ArrayBezierSpline2,
    *,
    samples: int | None = None,
    tolerance: float | None = None,
) -> ArrayPolyline2:
    """Sample a spline into a polyline with fixed or tolerance-driven density."""
    if samples is None:
        if tolerance is not None:
            if tolerance <= 0.0:
                raise ValueError("tolerance must be positive")
            samples_per_segment = max(4, int(ceil(1.0 / sqrt(tolerance))))
        else:
            samples_per_segment = 16
        samples = spline.segment_count * samples_per_segment + 1
    if samples < 2:
        raise ValueError("samples must be at least 2")

    vertices = evaluate_bezier_spline2(spline, np.linspace(0.0, 1.0, samples))
    if spline.closed and not np.allclose(vertices[0], vertices[-1]):
        vertices = np.vstack([vertices, vertices[0]])
    return ArrayPolyline2(vertices, closed=spline.closed)


@dataclass(frozen=True, slots=True)
class ArrayPolyline2:
    """Validated 2D polyline data with optional closure metadata."""

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
    """Validated polygon data with one outer ring and optional holes."""

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
