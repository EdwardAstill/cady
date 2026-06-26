from __future__ import annotations

from typing import cast

import numpy as np

from cady.operations.types import EdgeArray, FaceArray, Matrix3, Matrix4, PointArray2, PointArray3


def _as_float_array(value: object, *, name: str) -> np.ndarray:
    try:
        array = np.array(value, dtype=np.float64, copy=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    return array


def as_points2(value: object, *, name: str = "points") -> PointArray2:
    array = _as_float_array(value, name=name)
    if array.ndim != 2:
        raise ValueError(f"{name} must have rank 2")
    if array.shape[1] != 2:
        raise ValueError(f"{name} must have shape (n, 2)")
    return cast(PointArray2, array)


def as_points3(value: object, *, name: str = "points") -> PointArray3:
    array = _as_float_array(value, name=name)
    if array.ndim != 2:
        raise ValueError(f"{name} must have rank 2")
    if array.shape[1] != 3:
        raise ValueError(f"{name} must have shape (n, 3)")
    return cast(PointArray3, array)


def as_faces(value: object, *, name: str = "faces") -> FaceArray:
    raw = _as_float_array(value, name=name)
    if raw.ndim != 2:
        raise ValueError(f"{name} must have rank 2")
    if raw.shape[1] != 3:
        raise ValueError(f"{name} must have shape (n, 3)")
    if not np.all(raw == np.floor(raw)):
        raise ValueError(f"{name} must contain integer indices")
    return np.array(raw, dtype=np.int64, copy=True)


def as_edges(value: object, *, name: str = "edges") -> EdgeArray:
    raw = _as_float_array(value, name=name)
    if raw.ndim != 2:
        raise ValueError(f"{name} must have rank 2")
    if raw.shape[1] != 2:
        raise ValueError(f"{name} must have shape (n, 2)")
    if not np.all(raw == np.floor(raw)):
        raise ValueError(f"{name} must contain integer indices")
    return np.array(raw, dtype=np.int64, copy=True)


def as_matrix3(value: object, *, name: str = "matrix") -> Matrix3:
    array = _as_float_array(value, name=name)
    if array.shape != (3, 3):
        raise ValueError(f"{name} must have shape (3, 3)")
    return cast(Matrix3, array)


def as_matrix4(value: object, *, name: str = "matrix") -> Matrix4:
    array = _as_float_array(value, name=name)
    if array.shape != (4, 4):
        raise ValueError(f"{name} must have shape (4, 4)")
    return cast(Matrix4, array)
