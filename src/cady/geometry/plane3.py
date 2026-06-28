"""Local 3D coordinate planes for placing planar geometry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from cady.operations.coordinates import add3, cross3, dot3, normalised3, scale3, sub3
from cady.operations.transforms import Transform3

Point3: TypeAlias = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class Plane3:
    """Right-handed 3D plane with an origin, x-axis, and surface normal."""

    origin: Point3
    x_axis: Point3
    normal: Point3

    def __post_init__(self) -> None:
        origin = self.origin
        normal = normalised3(self.normal)
        x_axis = _orthogonal_x_axis(self.x_axis, normal)
        object.__setattr__(self, "origin", origin)
        object.__setattr__(self, "x_axis", x_axis)
        object.__setattr__(self, "normal", normal)

    @property
    def y_axis(self) -> Point3:
        return normalised3(cross3(self.normal, self.x_axis))

    @classmethod
    def world_xy(cls) -> Plane3:
        return cls((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))

    @classmethod
    def from_normal(
        cls,
        origin: Point3,
        normal: Point3,
        *,
        x_axis: Point3 | None = None,
    ) -> Plane3:
        normal_vec = normalised3(normal)
        x_axis_vec = (
            x_axis
            if x_axis is not None
            else _fallback_x_axis(normal_vec)
        )
        return cls(origin, x_axis_vec, normal_vec)

    def point(self, u: float, v: float) -> Point3:
        return add3(add3(self.origin, scale3(self.x_axis, float(u))), scale3(self.y_axis, float(v)))

    def transformed(self, transform: Transform3) -> Plane3:
        origin = _transform_point(transform, self.origin)
        x_point = _transform_point(transform, add3(self.origin, self.x_axis))
        normal_point = _transform_point(transform, add3(self.origin, self.normal))
        return Plane3(origin, sub3(x_point, origin), sub3(normal_point, origin))


def _orthogonal_x_axis(x_axis: Point3, normal: Point3) -> Point3:
    projected = sub3(x_axis, scale3(normal, dot3(x_axis, normal)))
    try:
        return normalised3(projected)
    except ValueError:
        return _fallback_x_axis(normal)


def _fallback_x_axis(normal: Point3) -> Point3:
    candidate = (1.0, 0.0, 0.0)
    if abs(dot3(normal, candidate)) > 0.9:
        candidate = (0.0, 1.0, 0.0)
    return normalised3(sub3(candidate, scale3(normal, dot3(candidate, normal))))


def _transform_point(transform: Transform3, point: Point3) -> Point3:
    array = transform.apply_points([point])
    return (float(array[0, 0]), float(array[0, 1]), float(array[0, 2]))
