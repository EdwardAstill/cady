"""Chainable 2D and 3D point-array transforms."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, sin
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray

Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]
Array: TypeAlias = NDArray[np.float64]


@dataclass(frozen=True, slots=True, init=False)
class Transform2:
    """Immutable chainable transformation for 2D point arrays."""

    points: Array | None
    matrix: Array

    def __init__(self, points: object | None = None, matrix: object | None = None) -> None:
        point_array = None
        if points is not None:
            point_array = np.array(points, dtype=np.float64, copy=True)
            if not np.all(np.isfinite(point_array)):
                raise ValueError("points must contain only finite values")
            if point_array.ndim != 2:
                raise ValueError("points must have rank 2")
            if point_array.shape[1] != 2:
                raise ValueError("points must have shape (n, 2)")

        matrix_array = np.eye(3, dtype=np.float64)
        if matrix is not None:
            matrix_array = np.array(matrix, dtype=np.float64, copy=True)
            if not np.all(np.isfinite(matrix_array)):
                raise ValueError("matrix must contain only finite values")
            if matrix_array.shape != (3, 3):
                raise ValueError("matrix must have shape (3, 3)")

        object.__setattr__(self, "points", point_array)
        object.__setattr__(self, "matrix", matrix_array)

    @property
    def array(self) -> Array:
        if self.points is None:
            raise ValueError("Transform2 has no points")
        return self.apply_points(self.points)

    def with_points(self, points: object) -> Transform2:
        return type(self)(points, self.matrix)

    def translate(self, dx: float, dy: float) -> Transform2:
        matrix = np.eye(3, dtype=np.float64)
        offset = np.array((dx, dy), dtype=np.float64, copy=True)
        if not np.all(np.isfinite(offset)):
            raise ValueError("offset must be a finite 2D vector")
        matrix[:2, 2] = offset
        return self._append(matrix)

    def rotate(self, angle: float, center: object = (0.0, 0.0)) -> Transform2:
        center_array = np.array(center, dtype=np.float64, copy=True)
        if center_array.shape != (2,) or not np.all(np.isfinite(center_array)):
            raise ValueError("center must be a finite 2D vector")
        matrix = np.eye(3, dtype=np.float64)
        matrix[:2, :2] = _rotation2(angle)
        return self._append(_around2(matrix, center_array))

    def scale(
        self,
        sx: float,
        sy: float | None = None,
        center: object = (0.0, 0.0),
    ) -> Transform2:
        center_array = np.array(center, dtype=np.float64, copy=True)
        if center_array.shape != (2,) or not np.all(np.isfinite(center_array)):
            raise ValueError("center must be a finite 2D vector")
        y_scale = sx if sy is None else sy
        matrix = np.diag([float(sx), float(y_scale), 1.0]).astype(np.float64)
        return self._append(_around2(matrix, center_array))

    def mirror(self, point: object, direction: object) -> Transform2:
        point_array = np.array(point, dtype=np.float64, copy=True)
        if point_array.shape != (2,) or not np.all(np.isfinite(point_array)):
            raise ValueError("point must be a finite 2D vector")
        unit = _unit(direction, dimensions=2, name="direction")
        matrix = np.eye(3, dtype=np.float64)
        matrix[:2, :2] = 2.0 * np.outer(unit, unit) - np.eye(2, dtype=np.float64)
        return self._append(_around2(matrix, point_array))

    def transform(self, matrix: object) -> Transform2:
        affine = np.eye(3, dtype=np.float64)
        linear = np.array(matrix, dtype=np.float64, copy=True)
        if linear.shape != (2, 2) or not np.all(np.isfinite(linear)):
            raise ValueError("matrix must have shape (2, 2)")
        affine[:2, :2] = linear
        return self._append(affine)

    def compose(self, other: Transform2) -> Transform2:
        return type(self)(self.points, self.matrix @ other.matrix)

    def inverse(self) -> Transform2:
        return type(self)(self.points, np.linalg.inv(self.matrix))

    def apply_points(self, points: object) -> Array:
        array = np.array(points, dtype=np.float64, copy=True)
        if not np.all(np.isfinite(array)):
            raise ValueError("points must contain only finite values")
        if array.ndim != 2:
            raise ValueError("points must have rank 2")
        if array.shape[1] != 2:
            raise ValueError("points must have shape (n, 2)")
        homogeneous = np.ones((len(array), 3), dtype=np.float64)
        homogeneous[:, :2] = array
        transformed = homogeneous @ self.matrix.T
        return transformed[:, :2]

    def _append(self, operation: Array) -> Transform2:
        return type(self)(self.points, operation @ self.matrix)


@dataclass(frozen=True, slots=True, init=False)
class Transform3:
    """Immutable chainable transformation for 3D point arrays."""

    points: Array | None
    matrix: Array

    def __init__(self, points: object | None = None, matrix: object | None = None) -> None:
        point_array = None
        if points is not None:
            point_array = np.array(points, dtype=np.float64, copy=True)
            if not np.all(np.isfinite(point_array)):
                raise ValueError("points must contain only finite values")
            if point_array.ndim != 2:
                raise ValueError("points must have rank 2")
            if point_array.shape[1] != 3:
                raise ValueError("points must have shape (n, 3)")

        matrix_array = np.eye(4, dtype=np.float64)
        if matrix is not None:
            matrix_array = np.array(matrix, dtype=np.float64, copy=True)
            if not np.all(np.isfinite(matrix_array)):
                raise ValueError("matrix must contain only finite values")
            if matrix_array.shape != (4, 4):
                raise ValueError("matrix must have shape (4, 4)")

        object.__setattr__(self, "points", point_array)
        object.__setattr__(self, "matrix", matrix_array)

    @classmethod
    def coerce(cls, value: object | None, *, allow_none: bool = False) -> Transform3:
        if value is None:
            if allow_none:
                return cls()
            raise TypeError("value must not be None")
        if isinstance(value, cls):
            return value
        try:
            return cls(matrix=value)
        except ValueError:
            pass
        matrix = getattr(value, "matrix", None)
        if matrix is not None:
            try:
                return cls(matrix=matrix)
            except ValueError:
                pass
        to_transform3 = getattr(value, "to_transform3", None)
        if callable(to_transform3):
            transformed = to_transform3()
            if isinstance(transformed, cls):
                return transformed
            matrix = getattr(transformed, "matrix", None)
            if matrix is not None:
                try:
                    return cls(matrix=matrix)
                except ValueError:
                    pass
        try:
            values = tuple(float(component) for component in value)  # type: ignore[reportUnknownVariableType]
        except TypeError:
            values = ()
        if len(values) == 3:
            return cls().translate(values[0], values[1], values[2])
        raise TypeError("value must be Transform3-like or a 3D translation")

    @property
    def array(self) -> Array:
        if self.points is None:
            raise ValueError("Transform3 has no points")
        return self.apply_points(self.points)

    def with_points(self, points: object) -> Transform3:
        return type(self)(points, self.matrix)

    def translate(self, dx: float, dy: float, dz: float) -> Transform3:
        matrix = np.eye(4, dtype=np.float64)
        offset = np.array((dx, dy, dz), dtype=np.float64, copy=True)
        if not np.all(np.isfinite(offset)):
            raise ValueError("offset must be a finite 3D vector")
        matrix[:3, 3] = offset
        return self._append(matrix)

    def rotate(
        self,
        *,
        axis_dir: object,
        angle: float,
        axis_origin: object = (0.0, 0.0, 0.0),
    ) -> Transform3:
        origin = np.array(axis_origin, dtype=np.float64, copy=True)
        if origin.shape != (3,) or not np.all(np.isfinite(origin)):
            raise ValueError("axis_origin must be a finite 3D vector")
        matrix = np.eye(4, dtype=np.float64)
        matrix[:3, :3] = _rotation3(axis_dir, angle)
        return self._append(_around3(matrix, origin))

    def scale(
        self,
        sx: float,
        sy: float | None = None,
        sz: float | None = None,
        center: object = (0.0, 0.0, 0.0),
    ) -> Transform3:
        center_array = np.array(center, dtype=np.float64, copy=True)
        if center_array.shape != (3,) or not np.all(np.isfinite(center_array)):
            raise ValueError("center must be a finite 3D vector")
        y_scale = sx if sy is None else sy
        z_scale = sx if sz is None else sz
        matrix = np.diag([float(sx), float(y_scale), float(z_scale), 1.0]).astype(
            np.float64
        )
        return self._append(_around3(matrix, center_array))

    def mirror(self, plane_origin: object, plane_normal: object) -> Transform3:
        origin = np.array(plane_origin, dtype=np.float64, copy=True)
        if origin.shape != (3,) or not np.all(np.isfinite(origin)):
            raise ValueError("plane_origin must be a finite 3D vector")
        normal = _unit(plane_normal, dimensions=3, name="plane_normal")
        matrix = np.eye(4, dtype=np.float64)
        matrix[:3, :3] = np.eye(3, dtype=np.float64) - 2.0 * np.outer(normal, normal)
        return self._append(_around3(matrix, origin))

    def transform(self, matrix: object) -> Transform3:
        affine = np.eye(4, dtype=np.float64)
        linear = np.array(matrix, dtype=np.float64, copy=True)
        if linear.shape != (3, 3) or not np.all(np.isfinite(linear)):
            raise ValueError("matrix must have shape (3, 3)")
        affine[:3, :3] = linear
        return self._append(affine)

    def compose(self, other: Transform3) -> Transform3:
        return type(self)(self.points, self.matrix @ other.matrix)

    def inverse(self) -> Transform3:
        return type(self)(self.points, np.linalg.inv(self.matrix))

    def apply_points(self, points: object) -> Array:
        array = np.array(points, dtype=np.float64, copy=True)
        if not np.all(np.isfinite(array)):
            raise ValueError("points must contain only finite values")
        if array.ndim != 2:
            raise ValueError("points must have rank 2")
        if array.shape[1] != 3:
            raise ValueError("points must have shape (n, 3)")
        homogeneous = np.ones((len(array), 4), dtype=np.float64)
        homogeneous[:, :3] = array
        transformed = homogeneous @ self.matrix.T
        return transformed[:, :3]

    def to_transform3(self) -> Transform3:
        return self

    def _append(self, operation: Array) -> Transform3:
        return type(self)(self.points, operation @ self.matrix)


def _rotation2(angle: float) -> Array:
    cosine = cos(angle)
    sine = sin(angle)
    return np.array(
        [
            [cosine, -sine],
            [sine, cosine],
        ],
        dtype=np.float64,
    )


def _rotation3(axis_dir: object, angle: float) -> Array:
    direction = _unit(axis_dir, dimensions=3, name="axis_dir")
    x_axis, y_axis, z_axis = direction
    cosine = cos(angle)
    sine = sin(angle)
    one_minus_cosine = 1.0 - cosine
    return np.array(
        [
            [
                cosine + x_axis * x_axis * one_minus_cosine,
                x_axis * y_axis * one_minus_cosine - z_axis * sine,
                x_axis * z_axis * one_minus_cosine + y_axis * sine,
            ],
            [
                y_axis * x_axis * one_minus_cosine + z_axis * sine,
                cosine + y_axis * y_axis * one_minus_cosine,
                y_axis * z_axis * one_minus_cosine - x_axis * sine,
            ],
            [
                z_axis * x_axis * one_minus_cosine - y_axis * sine,
                z_axis * y_axis * one_minus_cosine + x_axis * sine,
                cosine + z_axis * z_axis * one_minus_cosine,
            ],
        ],
        dtype=np.float64,
    )


def _around2(
    matrix: Array,
    center: Array,
) -> Array:
    return _translation2(center) @ matrix @ _translation2(-center)


def _around3(
    matrix: Array,
    center: Array,
) -> Array:
    return _translation3(center) @ matrix @ _translation3(-center)


def _translation2(offset: Array) -> Array:
    matrix = np.eye(3, dtype=np.float64)
    matrix[:2, 2] = offset
    return matrix


def _translation3(offset: Array) -> Array:
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, 3] = offset
    return matrix


def _unit(value: object, *, dimensions: int, name: str) -> Array:
    vector = np.array(value, dtype=np.float64, copy=True)
    if vector.shape != (dimensions,) or not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must be a finite {dimensions}D vector")
    length = float(np.linalg.norm(vector))
    if length == 0.0:
        raise ValueError(f"{name} must be non-zero")
    return np.array(vector / length, dtype=np.float64, copy=True)
