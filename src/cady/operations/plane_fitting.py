"""Primitive fitted-plane frames and coordinate conversion helpers."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import TypeAlias

import numpy as np

from cady.operations.primitives import add3, cross3, dot3, normalised3, scale3, sub3

Coordinate3: TypeAlias = Sequence[float]
Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class PlaneFrame:
    """Primitive right-handed frame fitted to 3D coordinates."""

    origin: Coordinate3
    normal: Coordinate3
    x_axis: Coordinate3
    y_axis: Coordinate3


def fit_plane(points: Iterable[Coordinate3]) -> PlaneFrame:
    """Fit a local plane frame to at least three finite 3D coordinates."""
    point_array = np.array(tuple(points), dtype=np.float64, copy=True)
    if len(point_array) < 3:
        raise ValueError("plane fit requires at least three points")
    if point_array.ndim != 2 or point_array.shape[1] != 3:
        raise ValueError("plane fit points must have shape (n, 3)")
    if not np.all(np.isfinite(point_array)):
        raise ValueError("plane fit points must be finite")

    centroid = point_array.mean(axis=0)
    centered = point_array - centroid
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    normal_array = vt[-1]
    if float(np.dot(normal_array, np.array([0.0, 0.0, 1.0]))) < 0.0:
        normal_array = -normal_array

    origin = (float(centroid[0]), float(centroid[1]), float(centroid[2]))
    normal = normalised3(
        (float(normal_array[0]), float(normal_array[1]), float(normal_array[2]))
    )
    x_axis = _fallback_x_axis(normal)
    y_axis = normalised3(cross3(normal, x_axis))
    return PlaneFrame(origin, normal, x_axis, y_axis)


def plane_coordinates(frame: PlaneFrame, point: Coordinate3) -> Point2:
    """Return local ``(u, v)`` coordinates for a point in a plane frame."""
    offset = sub3(point, frame.origin)
    return (dot3(offset, frame.x_axis), dot3(offset, frame.y_axis))


def plane_point(frame: PlaneFrame, u: float, v: float) -> Point3:
    """Return the 3D point at local coordinates ``(u, v)``."""
    return add3(
        add3(frame.origin, scale3(frame.x_axis, float(u))),
        scale3(frame.y_axis, float(v)),
    )


def plane_max_deviation(frame: PlaneFrame, points: Iterable[Coordinate3]) -> float:
    """Return the maximum absolute point distance from a plane frame."""
    point_tuple = tuple(points)
    if not point_tuple:
        raise ValueError("plane deviation requires at least one point")
    return max(
        abs(dot3(sub3(point, frame.origin), frame.normal)) for point in point_tuple
    )


def _fallback_x_axis(normal: Coordinate3) -> Point3:
    candidate: Point3 = (1.0, 0.0, 0.0)
    if abs(dot3(normal, candidate)) > 0.9:
        candidate = (0.0, 1.0, 0.0)
    return normalised3(sub3(candidate, scale3(normal, dot3(candidate, normal))))
