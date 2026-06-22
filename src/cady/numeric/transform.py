from __future__ import annotations

from dataclasses import dataclass
from math import cos, sin

import numpy as np

from cady.numeric.types import FloatArray, Matrix3, Matrix4, PointArray2, PointArray3
from cady.numeric.validation import as_matrix3, as_matrix4, as_points2, as_points3


def _vector2(value: object, *, name: str) -> PointArray2:
    array = np.array(value, dtype=np.float64, copy=True)
    if array.shape != (2,) or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a finite 2D vector")
    return array


def _vector3(value: object, *, name: str) -> PointArray3:
    array = np.array(value, dtype=np.float64, copy=True)
    if array.shape != (3,) or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a finite 3D vector")
    return array


def _unit2(value: object, *, name: str) -> PointArray2:
    vector = _vector2(value, name=name)
    length = float(np.linalg.norm(vector))
    if length == 0.0:
        raise ValueError(f"{name} must be non-zero")
    return np.array(vector / length, dtype=np.float64, copy=True)


def _unit3(value: object, *, name: str) -> PointArray3:
    vector = _vector3(value, name=name)
    length = float(np.linalg.norm(vector))
    if length == 0.0:
        raise ValueError(f"{name} must be non-zero")
    return np.array(vector / length, dtype=np.float64, copy=True)


@dataclass(frozen=True, slots=True)
class Transform2:
    matrix: Matrix3

    def __post_init__(self) -> None:
        object.__setattr__(self, "matrix", as_matrix3(self.matrix))

    @classmethod
    def identity(cls) -> Transform2:
        return cls(np.eye(3, dtype=np.float64))

    @classmethod
    def translation(cls, dx: float, dy: float) -> Transform2:
        matrix = np.eye(3, dtype=np.float64)
        matrix[:2, 2] = [dx, dy]
        return cls(matrix)

    @classmethod
    def rotation(cls, angle: float, centre: object = (0.0, 0.0)) -> Transform2:
        centre_array = _vector2(centre, name="centre")
        cosine = cos(angle)
        sine = sin(angle)
        matrix = np.array(
            [
                [cosine, -sine, 0.0],
                [sine, cosine, 0.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        return cls.translation(float(centre_array[0]), float(centre_array[1])).compose(
            cls(matrix)
        ).compose(cls.translation(float(-centre_array[0]), float(-centre_array[1])))

    @classmethod
    def scale(
        cls,
        sx: float,
        sy: float | None = None,
        centre: object = (0.0, 0.0),
    ) -> Transform2:
        centre_array = _vector2(centre, name="centre")
        y_scale = sx if sy is None else sy
        matrix = np.array(
            [
                [sx, 0.0, 0.0],
                [0.0, y_scale, 0.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        return cls.translation(float(centre_array[0]), float(centre_array[1])).compose(
            cls(matrix)
        ).compose(cls.translation(float(-centre_array[0]), float(-centre_array[1])))

    @classmethod
    def mirror(cls, point: object, direction: object) -> Transform2:
        point_array = _vector2(point, name="point")
        unit = _unit2(direction, name="direction")
        reflection = 2.0 * np.outer(unit, unit) - np.eye(2, dtype=np.float64)
        matrix = np.eye(3, dtype=np.float64)
        matrix[:2, :2] = reflection
        return cls.translation(float(point_array[0]), float(point_array[1])).compose(
            cls(matrix)
        ).compose(cls.translation(float(-point_array[0]), float(-point_array[1])))

    def compose(self, other: Transform2) -> Transform2:
        return Transform2(self.matrix @ other.matrix)

    def inverse(self) -> Transform2:
        return Transform2(as_matrix3(np.linalg.inv(self.matrix)))

    def apply_points(self, points: object) -> PointArray2:
        array = as_points2(points)
        homogeneous = np.ones((len(array), 3), dtype=np.float64)
        homogeneous[:, :2] = array
        transformed = homogeneous @ self.matrix.T
        return transformed[:, :2]


@dataclass(frozen=True, slots=True)
class Transform3:
    matrix: Matrix4

    def __post_init__(self) -> None:
        object.__setattr__(self, "matrix", as_matrix4(self.matrix))

    @classmethod
    def identity(cls) -> Transform3:
        return cls(np.eye(4, dtype=np.float64))

    @classmethod
    def translation(cls, dx: float, dy: float, dz: float) -> Transform3:
        matrix = np.eye(4, dtype=np.float64)
        matrix[:3, 3] = [dx, dy, dz]
        return cls(matrix)

    @classmethod
    def rotation(cls, axis_origin: object, axis_dir: object, angle: float) -> Transform3:
        origin = _vector3(axis_origin, name="axis_origin")
        direction = _unit3(axis_dir, name="axis_dir")
        x_axis, y_axis, z_axis = direction
        cosine = cos(angle)
        sine = sin(angle)
        one_minus_cosine = 1.0 - cosine
        rotation = np.array(
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
        matrix = np.eye(4, dtype=np.float64)
        matrix[:3, :3] = rotation
        return cls.translation(float(origin[0]), float(origin[1]), float(origin[2])).compose(
            cls(matrix)
        ).compose(cls.translation(float(-origin[0]), float(-origin[1]), float(-origin[2])))

    @classmethod
    def scale(
        cls,
        sx: float,
        sy: float | None = None,
        sz: float | None = None,
        centre: object = (0.0, 0.0, 0.0),
    ) -> Transform3:
        centre_array = _vector3(centre, name="centre")
        y_scale = sx if sy is None else sy
        z_scale = sx if sz is None else sz
        matrix = np.array(np.diag([sx, y_scale, z_scale, 1.0]), dtype=np.float64, copy=True)
        return cls.translation(
            float(centre_array[0]), float(centre_array[1]), float(centre_array[2])
        ).compose(cls(matrix)).compose(
            cls.translation(
                float(-centre_array[0]), float(-centre_array[1]), float(-centre_array[2])
            )
        )

    @classmethod
    def mirror(cls, plane_origin: object, plane_normal: object) -> Transform3:
        origin = _vector3(plane_origin, name="plane_origin")
        normal = _unit3(plane_normal, name="plane_normal")
        reflection = np.eye(3, dtype=np.float64) - 2.0 * np.outer(normal, normal)
        matrix = np.eye(4, dtype=np.float64)
        matrix[:3, :3] = reflection
        return cls.translation(float(origin[0]), float(origin[1]), float(origin[2])).compose(
            cls(matrix)
        ).compose(cls.translation(float(-origin[0]), float(-origin[1]), float(-origin[2])))

    def compose(self, other: Transform3) -> Transform3:
        return Transform3(self.matrix @ other.matrix)

    def inverse(self) -> Transform3:
        return Transform3(as_matrix4(np.linalg.inv(self.matrix)))

    def apply_points(self, points: object) -> PointArray3:
        array = as_points3(points)
        homogeneous = np.ones((len(array), 4), dtype=np.float64)
        homogeneous[:, :3] = array
        transformed = homogeneous @ self.matrix.T
        return transformed[:, :3]


@dataclass(frozen=True, slots=True)
class Pose3:
    rotation: Matrix3
    translation: FloatArray

    def __post_init__(self) -> None:
        rotation = as_matrix3(self.rotation, name="rotation")
        translation = _vector3(self.translation, name="translation")
        object.__setattr__(self, "rotation", rotation)
        object.__setattr__(self, "translation", translation)

    @classmethod
    def identity(cls) -> Pose3:
        return cls(np.eye(3, dtype=np.float64), np.zeros(3, dtype=np.float64))

    def to_transform3(self) -> Transform3:
        matrix = np.eye(4, dtype=np.float64)
        matrix[:3, :3] = self.rotation
        matrix[:3, 3] = self.translation
        return Transform3(matrix)

    def apply_points(self, points: object) -> PointArray3:
        array = as_points3(points)
        return array @ self.rotation.T + self.translation
