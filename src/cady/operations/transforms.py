"""Point-level transforms and validated affine transform containers."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, sin

import numpy as np

from cady.operations.types import (
    FloatArray,
    Matrix3,
    Matrix4,
    Point2,
    Point3,
    PointArray2,
    PointArray3,
)
from cady.operations.validation import as_matrix3, as_matrix4, as_points2, as_points3


def translate_point2(point: Point2, dx: float, dy: float) -> Point2:
    return (point[0] + dx, point[1] + dy)


def rotate_point2(point: Point2, centre: Point2, angle: float) -> Point2:
    ca = cos(angle)
    sa = sin(angle)
    rel_x = point[0] - centre[0]
    rel_y = point[1] - centre[1]
    return (centre[0] + rel_x * ca - rel_y * sa, centre[1] + rel_x * sa + rel_y * ca)


def scale_point2(point: Point2, sx: float, sy: float, centre: Point2) -> Point2:
    return (centre[0] + (point[0] - centre[0]) * sx, centre[1] + (point[1] - centre[1]) * sy)


def mirror_point2(point: Point2, a: Point2, b: Point2) -> Point2:
    axis = _normalised2((b[0] - a[0], b[1] - a[1]))
    rel = (point[0] - a[0], point[1] - a[1])
    projected = (a[0] + axis[0] * _dot2(rel, axis), a[1] + axis[1] * _dot2(rel, axis))
    return (projected[0] * 2 - point[0], projected[1] * 2 - point[1])


def translate_point3(point: Point3, dx: float, dy: float, dz: float) -> Point3:
    return (point[0] + dx, point[1] + dy, point[2] + dz)


def rotate_point3(point: Point3, axis_origin: Point3, axis_dir: Point3, angle: float) -> Point3:
    direction = _normalised3(axis_dir)
    ca = cos(angle)
    sa = sin(angle)
    rel = (point[0] - axis_origin[0], point[1] - axis_origin[1], point[2] - axis_origin[2])
    cross = _cross3(direction, rel)
    dot = _dot3(direction, rel)
    rotated = (
        rel[0] * ca + cross[0] * sa + direction[0] * (dot * (1 - ca)),
        rel[1] * ca + cross[1] * sa + direction[1] * (dot * (1 - ca)),
        rel[2] * ca + cross[2] * sa + direction[2] * (dot * (1 - ca)),
    )
    return (
        axis_origin[0] + rotated[0],
        axis_origin[1] + rotated[1],
        axis_origin[2] + rotated[2],
    )


def mirror_point3(point: Point3, plane_origin: Point3, plane_normal: Point3) -> Point3:
    normal = _normalised3(plane_normal)
    rel = (
        point[0] - plane_origin[0],
        point[1] - plane_origin[1],
        point[2] - plane_origin[2],
    )
    distance = 2 * _dot3(rel, normal)
    return (
        point[0] - normal[0] * distance,
        point[1] - normal[1] * distance,
        point[2] - normal[2] * distance,
    )


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


def _dot2(a: Point2, b: Point2) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _normalised2(a: Point2) -> Point2:
    length = _dot2(a, a) ** 0.5
    if length == 0:
        raise ValueError("zero-length vector")
    return (a[0] / length, a[1] / length)


def _dot3(a: Point3, b: Point3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross3(a: Point3, b: Point3) -> Point3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _normalised3(a: Point3) -> Point3:
    length = _dot3(a, a) ** 0.5
    if length == 0:
        raise ValueError("zero-length vector")
    return (a[0] / length, a[1] / length, a[2] / length)


@dataclass(frozen=True, slots=True)
class Transform2:
    """Homogeneous 2D affine transform wrapper."""

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
    """Homogeneous 3D affine transform wrapper."""

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


def coerce_transform3(value: object | None, *, allow_none: bool = False) -> Transform3:
    """Coerce a transform, pose-like object, or translation tuple into ``Transform3``."""
    if value is None:
        if allow_none:
            return Transform3.identity()
        raise TypeError("value must not be None")
    if isinstance(value, Transform3):
        return value
    to_transform3 = getattr(value, "to_transform3", None)
    if callable(to_transform3):
        transform = to_transform3()
        if isinstance(transform, Transform3):
            return transform
    try:
        values = tuple(float(component) for component in value)  # type: ignore[reportUnknownVariableType]
    except TypeError:
        values = ()
    if len(values) == 3:
        return Transform3.translation(values[0], values[1], values[2])
    raise TypeError("value must be Transform3, Pose3-like, or a 3D translation")


@dataclass(frozen=True, slots=True)
class Pose3:
    """Rigid 3D pose stored as rotation matrix plus translation."""

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
