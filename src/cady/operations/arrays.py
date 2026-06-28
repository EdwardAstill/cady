"""Array-backed numeric containers and validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, sqrt
from typing import Protocol, cast

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]
PointArray2 = NDArray[np.float64]
PointArray3 = NDArray[np.float64]
FaceArray = NDArray[np.int64]
EdgeArray = NDArray[np.int64]
Matrix3 = NDArray[np.float64]
Matrix4 = NDArray[np.float64]

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]


class _PointTransform(Protocol):
    def apply_points(self, points: np.ndarray) -> np.ndarray: ...


def _as_float_array(value: object, *, name: str) -> np.ndarray:
    try:
        array = np.array(value, dtype=np.float64, copy=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    return array


def as_points2(value: object, *, name: str = "points") -> PointArray2:
    """Validate an ``(n, 2)`` float array of 2D points."""
    array = _as_float_array(value, name=name)
    if array.ndim != 2:
        raise ValueError(f"{name} must have rank 2")
    if array.shape[1] != 2:
        raise ValueError(f"{name} must have shape (n, 2)")
    return cast(PointArray2, array)


def as_points3(value: object, *, name: str = "points") -> PointArray3:
    """Validate an ``(n, 3)`` float array of 3D points."""
    array = _as_float_array(value, name=name)
    if array.ndim != 2:
        raise ValueError(f"{name} must have rank 2")
    if array.shape[1] != 3:
        raise ValueError(f"{name} must have shape (n, 3)")
    return cast(PointArray3, array)


def as_faces(value: object, *, name: str = "faces") -> FaceArray:
    """Validate an ``(n, 3)`` integer-like triangle index array."""
    raw = _as_float_array(value, name=name)
    if raw.ndim != 2:
        raise ValueError(f"{name} must have rank 2")
    if raw.shape[1] != 3:
        raise ValueError(f"{name} must have shape (n, 3)")
    if not np.all(raw == np.floor(raw)):
        raise ValueError(f"{name} must contain integer indices")
    return np.array(raw, dtype=np.int64, copy=True)


def as_edges(value: object, *, name: str = "edges") -> EdgeArray:
    """Validate an ``(n, 2)`` integer-like edge index array."""
    raw = _as_float_array(value, name=name)
    if raw.ndim != 2:
        raise ValueError(f"{name} must have rank 2")
    if raw.shape[1] != 2:
        raise ValueError(f"{name} must have shape (n, 2)")
    if not np.all(raw == np.floor(raw)):
        raise ValueError(f"{name} must contain integer indices")
    return np.array(raw, dtype=np.int64, copy=True)


def as_matrix3(value: object, *, name: str = "matrix") -> Matrix3:
    """Validate a 3x3 affine or rotation matrix."""
    array = _as_float_array(value, name=name)
    if array.shape != (3, 3):
        raise ValueError(f"{name} must have shape (3, 3)")
    return cast(Matrix3, array)


def as_matrix4(value: object, *, name: str = "matrix") -> Matrix4:
    """Validate a 4x4 affine transform matrix."""
    array = _as_float_array(value, name=name)
    if array.shape != (4, 4):
        raise ValueError(f"{name} must have shape (4, 4)")
    return cast(Matrix4, array)


def bounds2(points: object, *, name: str = "points") -> tuple[PointArray2, PointArray2]:
    """Return the minimum and maximum corners of a 2D point set."""
    array = as_points2(points, name=name)
    if len(array) == 0:
        raise ValueError(f"{name} must contain at least one point")
    return np.min(array, axis=0), np.max(array, axis=0)


def bounds3(points: object, *, name: str = "points") -> tuple[PointArray3, PointArray3]:
    """Return the minimum and maximum corners of a 3D point set."""
    array = as_points3(points, name=name)
    if len(array) == 0:
        raise ValueError(f"{name} must contain at least one point")
    return np.min(array, axis=0), np.max(array, axis=0)


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


def _closed_ring(points: PointArray2) -> PointArray2:
    if len(points) > 1 and np.allclose(points[0], points[-1]):
        return points[:-1]
    return points


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

    def transformed(self, transform: _PointTransform) -> ArrayBezierSpline2:
        return type(self)(transform.apply_points(self.control_points), closed=self.closed)

    def sample(
        self,
        *,
        samples: int | None = None,
        tolerance: float | None = None,
    ) -> PointArray2:
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
) -> PointArray2:
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
    return as_points2(vertices, name="vertices")


def polyline2_length(vertices: object, *, closed: bool = False) -> float:
    points = as_points2(vertices, name="vertices")
    if len(points) < 2:
        return 0.0
    segments = np.diff(points, axis=0)
    length = float(np.sum(np.linalg.norm(segments, axis=1)))
    if closed and len(points) > 2:
        length += float(np.linalg.norm(points[0] - points[-1]))
    return length


def polyline2_area(vertices: object) -> float:
    ring = _closed_ring(as_points2(vertices, name="vertices"))
    if len(ring) < 3:
        raise ValueError("closed polyline must contain at least three points")
    return abs(_ring_area(ring))


def polyline2_centroid(vertices: object) -> PointArray2:
    ring = _closed_ring(as_points2(vertices, name="vertices"))
    if len(ring) < 3:
        raise ValueError("closed polyline must contain at least three points")
    signed_area, centroid = _ring_centroid(ring)
    if signed_area == 0.0:
        raise ValueError("closed polyline area must be non-zero")
    return centroid


def polyline3_transformed(vertices: object, transform: _PointTransform) -> PointArray3:
    transformed = transform.apply_points(as_points3(vertices, name="vertices"))
    return as_points3(transformed, name="vertices")
