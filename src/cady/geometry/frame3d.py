from __future__ import annotations

from dataclasses import dataclass

from cady.operations.transforms import Transform3
from cady.vec import Vec3, promote3

Point3Like = Vec3 | tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class Frame3D:
    origin: Vec3
    x_axis: Vec3
    normal: Vec3

    def __post_init__(self) -> None:
        origin = promote3(self.origin)
        normal = promote3(self.normal).normalised()
        x_axis = _orthogonal_x_axis(promote3(self.x_axis), normal)
        object.__setattr__(self, "origin", origin)
        object.__setattr__(self, "x_axis", x_axis)
        object.__setattr__(self, "normal", normal)

    @property
    def y_axis(self) -> Vec3:
        return self.normal.cross(self.x_axis).normalised()

    @classmethod
    def world_xy(cls) -> Frame3D:
        return cls(Vec3(0.0, 0.0, 0.0), Vec3(1.0, 0.0, 0.0), Vec3(0.0, 0.0, 1.0))

    @classmethod
    def from_normal(
        cls,
        origin: Point3Like,
        normal: Point3Like,
        *,
        x_axis: Point3Like | None = None,
    ) -> Frame3D:
        normal_vec = promote3(normal).normalised()
        x_axis_vec = promote3(x_axis) if x_axis is not None else _fallback_x_axis(normal_vec)
        return cls(promote3(origin), x_axis_vec, normal_vec)

    def point(self, u: float, v: float) -> Vec3:
        return self.origin + self.x_axis * float(u) + self.y_axis * float(v)

    def transformed(self, transform: Transform3) -> Frame3D:
        origin = _transform_point(transform, self.origin)
        x_point = _transform_point(transform, self.origin + self.x_axis)
        normal_point = _transform_point(transform, self.origin + self.normal)
        return Frame3D(origin, x_point - origin, normal_point - origin)


def _orthogonal_x_axis(x_axis: Vec3, normal: Vec3) -> Vec3:
    projected = x_axis - normal * x_axis.dot(normal)
    try:
        return projected.normalised()
    except ValueError:
        return _fallback_x_axis(normal)


def _fallback_x_axis(normal: Vec3) -> Vec3:
    candidate = Vec3(1.0, 0.0, 0.0)
    if abs(normal.dot(candidate)) > 0.9:
        candidate = Vec3(0.0, 1.0, 0.0)
    return (candidate - normal * candidate.dot(normal)).normalised()


def _transform_point(transform: Transform3, point: Vec3) -> Vec3:
    array = transform.apply_points([point.tuple()])
    return Vec3(float(array[0, 0]), float(array[0, 1]), float(array[0, 2]))
