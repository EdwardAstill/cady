"""Local 3D coordinate planes for placing planar geometry."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from cady.geometry.point import Point2, Point3, point3
from cady.geometry.vector import Vector3, vector3
from cady.operations.plane_fitting import (
    PlaneFrame,
    fit_plane,
    plane_coordinates,
    plane_max_deviation,
    plane_point,
)
from cady.operations.primitives import add3, cross3, dot3, normalised3, scale3, sub3
from cady.operations.transforms import Transform3


@dataclass(frozen=True, slots=True, init=False)
class Plane3:
    """Right-handed 3D plane defined by a point and a normal vector."""

    origin: Point3
    normal: Vector3
    x_axis: Vector3

    def __init__(
        self,
        point: object,
        normal: object,
        *,
        x_axis: object | None = None,
    ) -> None:
        point = point3(point, name="point")
        normal = vector3(normalised3(vector3(normal, name="normal")), name="normal")
        x_axis = _orthogonal_x_axis(
            Vector3(1.0, 0.0, 0.0) if x_axis is None else vector3(x_axis, name="x_axis"),
            normal,
        )
        object.__setattr__(self, "origin", point)
        object.__setattr__(self, "x_axis", x_axis)
        object.__setattr__(self, "normal", normal)

    @property
    def y_axis(self) -> Vector3:
        return vector3(normalised3(cross3(self.normal, self.x_axis)), name="y_axis")

    @classmethod
    def world_xy(cls) -> Plane3:
        return cls((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), x_axis=(1.0, 0.0, 0.0))

    @classmethod
    def from_normal(
        cls,
        origin: object,
        normal: object,
        *,
        x_axis: object | None = None,
    ) -> Plane3:
        normal_vec = vector3(normalised3(vector3(normal, name="normal")), name="normal")
        x_axis_vec = (
            x_axis
            if x_axis is not None
            else _fallback_x_axis(normal_vec)
        )
        return cls(origin, normal_vec, x_axis=x_axis_vec)

    @classmethod
    def fit(cls, points: Iterable[object]) -> Plane3:
        """Fit a plane to 3D points and return its local frame."""
        point_tuple = tuple(point3(point) for point in points)
        frame = fit_plane(point_tuple)
        return cls(frame.origin, frame.normal, x_axis=frame.x_axis)

    def point(self, u: float, v: float) -> Point3:
        return point3(plane_point(_plane_frame(self), u, v))

    def coordinates(self, point: object) -> Point2:
        """Return plane-local ``(u, v)`` coordinates for a 3D point."""
        u, v = plane_coordinates(_plane_frame(self), point3(point))
        return Point2(u, v)

    def signed_distance(self, point: object) -> float:
        """Return signed distance from a 3D point to this plane."""
        return dot3(sub3(point3(point), self.origin), self.normal)

    def project(self, point: object) -> Point3:
        """Return the orthogonal projection of a 3D point onto this plane."""
        return point3(sub3(point3(point), scale3(self.normal, self.signed_distance(point))))

    def max_deviation(self, points: Iterable[object]) -> float:
        """Return the maximum absolute point distance from this plane."""
        return plane_max_deviation(
            _plane_frame(self),
            tuple(point3(point) for point in points),
        )

    def transformed(self, transform: Transform3) -> Plane3:
        origin = _transform_point(transform, self.origin)
        x_point = _transform_point(transform, add3(self.origin, self.x_axis))
        normal_point = _transform_point(transform, add3(self.origin, self.normal))
        return Plane3(origin, sub3(normal_point, origin), x_axis=sub3(x_point, origin))


def _orthogonal_x_axis(x_axis: Vector3, normal: Vector3) -> Vector3:
    projected = sub3(x_axis, scale3(normal, dot3(x_axis, normal)))
    try:
        return vector3(normalised3(projected), name="x_axis")
    except ValueError:
        return _fallback_x_axis(normal)


def _plane_frame(plane: Plane3) -> PlaneFrame:
    return PlaneFrame(plane.origin, plane.normal, plane.x_axis, plane.y_axis)


def _fallback_x_axis(normal: Vector3) -> Vector3:
    candidate = Vector3(1.0, 0.0, 0.0)
    if abs(dot3(normal, candidate)) > 0.9:
        candidate = Vector3(0.0, 1.0, 0.0)
    return vector3(
        normalised3(sub3(candidate, scale3(normal, dot3(candidate, normal)))),
        name="x_axis",
    )


def _transform_point(transform: Transform3, point: object) -> Point3:
    array = transform.apply_points([point])
    return Point3(float(array[0, 0]), float(array[0, 1]), float(array[0, 2]))
