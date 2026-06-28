"""Circular 2D and 3D arc geometry."""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, ceil, cos, pi, sin
from typing import TYPE_CHECKING, TypeAlias

from cady.operations.coordinates import add3, dot3, length3, scale3
from cady.operations.sampling import arc_points, segments_for_circle
from cady.utils import finite, positive, positive_tolerance

Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]

if TYPE_CHECKING:
    from cady.operations.arrays import PointArray2, PointArray3


def _unit_axis(axis: Point3, name: str) -> Point3:
    length = length3(axis)
    if length == 0.0:
        raise ValueError(f"{name} must not be zero length")
    return scale3(axis, 1.0 / length)


def _angle_in_sweep(angle: float, start_rad: float, end_rad: float) -> bool:
    sweep = end_rad - start_rad
    if abs(sweep) >= 2.0 * pi:
        return True
    if sweep > 0.0:
        return (angle - start_rad) % (2.0 * pi) <= sweep
    return (start_rad - angle) % (2.0 * pi) <= -sweep


@dataclass(frozen=True, slots=True, init=False)
class Arc2:
    """Circular 2D arc described by centre, radius, and sweep angles."""

    centre: Point2
    radius: float
    start_rad: float
    end_rad: float

    def __init__(
        self,
        centre: Point2,
        radius: float,
        start_rad: float,
        end_rad: float,
    ) -> None:
        radius = positive(radius, "radius")
        start_rad = finite(start_rad, "start_rad")
        end_rad = finite(end_rad, "end_rad")
        object.__setattr__(self, "centre", centre)
        object.__setattr__(self, "radius", radius)
        object.__setattr__(self, "start_rad", start_rad)
        object.__setattr__(self, "end_rad", end_rad)
        if start_rad == end_rad:
            raise ValueError("Arc2 start and end angles must differ")

    def _point(self, angle: float) -> Point2:
        return (
            self.centre[0] + self.radius * cos(angle),
            self.centre[1] + self.radius * sin(angle),
        )

    def bounds(self) -> tuple[Point2, Point2]:
        points = [self._point(self.start_rad), self._point(self.end_rad)]
        start = self.start_rad % (2 * pi)
        sweep = (self.end_rad - self.start_rad) % (2 * pi)
        for angle in (0.0, pi / 2.0, pi, 3.0 * pi / 2.0):
            if (angle - start) % (2 * pi) <= sweep:
                points.append(self._point(angle))
        return (
            (min(point[0] for point in points), min(point[1] for point in points)),
            (max(point[0] for point in points), max(point[1] for point in points)),
        )

    @property
    def boundary(self) -> tuple[Point2, Point2]:
        return self.bounds()

    def points(self) -> tuple[Point2, ...]:
        return (self._point(self.start_rad), self._point(self.end_rad))

    def to_array(self, *, tolerance: float) -> PointArray2:
        tolerance = positive_tolerance(tolerance)
        from cady.operations.arrays import as_points2

        points = tuple(
            (x, y)
            for x, y in arc_points(
                self.centre,
                self.radius,
                self.start_rad,
                self.end_rad,
                tolerance=tolerance,
            )
        )
        return as_points2(points, name="vertices")


@dataclass(frozen=True, slots=True, init=False)
class Arc3:
    """Circular 3D arc in the plane spanned by two perpendicular axes."""

    centre: Point3
    radius: float
    start_rad: float
    end_rad: float
    x_axis: Point3
    y_axis: Point3

    def __init__(
        self,
        centre: Point3,
        radius: float,
        start_rad: float,
        end_rad: float,
        *,
        x_axis: Point3 = (1.0, 0.0, 0.0),
        y_axis: Point3 = (0.0, 1.0, 0.0),
    ) -> None:
        radius = positive(radius, "radius")
        start_rad = finite(start_rad, "start_rad")
        end_rad = finite(end_rad, "end_rad")
        if start_rad == end_rad:
            raise ValueError("Arc3 start and end angles must differ")

        x = _unit_axis(x_axis, "x_axis")
        y = _unit_axis(y_axis, "y_axis")
        if abs(dot3(x, y)) > 1e-9:
            raise ValueError("Arc3 x_axis and y_axis must be perpendicular")

        object.__setattr__(self, "centre", centre)
        object.__setattr__(self, "radius", radius)
        object.__setattr__(self, "start_rad", start_rad)
        object.__setattr__(self, "end_rad", end_rad)
        object.__setattr__(self, "x_axis", x)
        object.__setattr__(self, "y_axis", y)

    def _point(self, angle: float) -> Point3:
        return add3(
            add3(self.centre, scale3(self.x_axis, self.radius * cos(angle))),
            scale3(self.y_axis, self.radius * sin(angle)),
        )

    def bounds(self) -> tuple[Point3, Point3]:
        candidate_angles = [self.start_rad, self.end_rad]
        axis_pairs = (
            (self.x_axis[0], self.y_axis[0]),
            (self.x_axis[1], self.y_axis[1]),
            (self.x_axis[2], self.y_axis[2]),
        )
        for x_component, y_component in axis_pairs:
            angle = atan2(y_component, x_component)
            for candidate in (angle, angle + pi):
                if _angle_in_sweep(candidate, self.start_rad, self.end_rad):
                    candidate_angles.append(candidate)
        points = tuple(self._point(angle) for angle in candidate_angles)
        return (
            (
                min(point[0] for point in points),
                min(point[1] for point in points),
                min(point[2] for point in points),
            ),
            (
                max(point[0] for point in points),
                max(point[1] for point in points),
                max(point[2] for point in points),
            ),
        )

    @property
    def boundary(self) -> tuple[Point3, Point3]:
        return self.bounds()

    def points(self) -> tuple[Point3, Point3]:
        return (self._point(self.start_rad), self._point(self.end_rad))

    def to_array(self, *, tolerance: float) -> PointArray3:
        tolerance = positive_tolerance(tolerance)

        from cady.operations.arrays import as_points3

        sweep = self.end_rad - self.start_rad
        segment_count = max(
            2,
            ceil(
                abs(sweep)
                / (2.0 * pi)
                * segments_for_circle(self.radius, tolerance)
            ),
        )
        points = [
            self._point(self.start_rad + sweep * index / segment_count)
            for index in range(segment_count + 1)
        ]
        return as_points3(points, name="vertices")


__all__ = ["Arc2", "Arc3"]
