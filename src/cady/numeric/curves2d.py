from __future__ import annotations

from dataclasses import dataclass
from math import ceil, sqrt
from typing import cast

import numpy as np

from cady.numeric.bounds import bounds2
from cady.numeric.paths2d import ArrayPolyline2
from cady.numeric.transform import Transform2
from cady.numeric.types import PointArray2
from cady.numeric.validation import as_points2


@dataclass(frozen=True, slots=True)
class ArrayBezierSpline2:
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
