"""Plane fitting and projection helpers for mesh operations."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

Point3Array = NDArray[np.float64]


def vector3(value: object, *, name: str) -> Point3Array:
    """Validate a single 3D vector-like input."""
    array = np.array(value, dtype=np.float64, copy=True)
    if array.shape != (3,) or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a finite 3D vector")
    return array


def unit3(value: object, *, name: str) -> Point3Array:
    """Validate and normalise a 3D vector-like input."""
    vector = vector3(value, name=name)
    length = float(np.linalg.norm(vector))
    if length == 0.0:
        raise ValueError(f"{name} must be non-zero")
    return vector / length


def basis_for_plane(normal: Point3Array) -> tuple[Point3Array, Point3Array]:
    """Build an orthonormal in-plane basis for a plane normal."""
    reference = (
        np.array([1.0, 0.0, 0.0], dtype=np.float64)
        if abs(float(normal[0])) < 0.9
        else np.array([0.0, 1.0, 0.0], dtype=np.float64)
    )
    u_axis = np.cross(normal, reference)
    u_axis = u_axis / np.linalg.norm(u_axis)
    v_axis = np.cross(normal, u_axis)
    return u_axis, v_axis


def project_loop(
    loop: list[int],
    vertices: list[Point3Array],
    origin: Point3Array,
    normal: Point3Array,
) -> list[tuple[float, float]]:
    """Project a 3D vertex loop into plane-local 2D coordinates."""
    u_axis, v_axis = basis_for_plane(normal)
    projected: list[tuple[float, float]] = []
    for vertex_index in loop:
        relative = vertices[vertex_index] - origin
        projected.append((float(np.dot(relative, u_axis)), float(np.dot(relative, v_axis))))
    return projected


def fit_plane_svd(points: Point3Array) -> tuple[Point3Array, Point3Array]:
    """Fit a plane to points via SVD. Returns (origin, normal)."""
    centroid = points.mean(axis=0)
    centered = points - centroid
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    normal = vt[-1]
    if float(np.dot(normal, np.array([0.0, 0.0, 1.0]))) < 0.0:
        normal = -normal
    return centroid, normal


def max_plane_deviation(
    points: Point3Array,
    origin: Point3Array,
    normal: Point3Array,
) -> float:
    """Return the maximum absolute distance of points from the plane."""
    return float(np.max(np.abs(np.dot(points - origin, normal))))


def project_point_to_plane(
    point: tuple[float, float, float],
    distance: float,
    normal: np.ndarray,
) -> tuple[float, float, float]:
    """Project a point along a plane normal by a signed distance."""
    return (
        point[0] - distance * float(normal[0]),
        point[1] - distance * float(normal[1]),
        point[2] - distance * float(normal[2]),
    )
