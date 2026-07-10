"""Circular 2D and 3D arc geometry."""

from __future__ import annotations

from dataclasses import dataclass
from math import acos, atan2, ceil, cos, pi, sin
from typing import TYPE_CHECKING, TypeAlias

from cady.geometry._coordinates import point2, point3
from cady.operations.primitives import add3, dot3, length3, scale3, sub3
from cady.utils import positive, positive_tolerance

Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]

if TYPE_CHECKING:
    from cady.geometry.polyline import Polyline2, Polyline3


def _angle_in_sweep(angle: float, start_rad: float, end_rad: float) -> bool:
    sweep = end_rad - start_rad
    if abs(sweep) >= 2.0 * pi:
        return True
    if sweep > 0.0:
        return (angle - start_rad) % (2.0 * pi) <= sweep
    return (start_rad - angle) % (2.0 * pi) <= -sweep


def _segments_for_circle(radius: float, tolerance: float) -> int:
    tolerance = max(float(tolerance), 1e-9)
    if tolerance >= radius:
        return 12
    angle = 2.0 * acos(max(-1.0, min(1.0, 1.0 - tolerance / radius)))
    return max(12, ceil((2.0 * pi) / angle))


def _min_segments(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("min_segments must be an integer")
    if value < 1:
        raise ValueError("min_segments must be at least 1")
    return value


def _segment_count(
    *,
    radius: float,
    sweep: float,
    tolerance: float,
    max_segment_length: float | None,
    min_segments: int,
) -> int:
    count = max(
        min_segments,
        ceil(abs(sweep) / (2.0 * pi) * _segments_for_circle(radius, tolerance)),
    )
    if max_segment_length is not None:
        count = max(
            count,
            ceil(abs(sweep) * radius / positive(max_segment_length, "max_segment_length")),
        )
    return max(1, count)


@dataclass(frozen=True, slots=True, init=False)
class Arc2:
    """Circular 2D arc described by center, start, and arc midpoint."""

    center: Point2
    start: Point2
    midpoint: Point2
    end: Point2
    radius: float
    start_rad: float
    end_rad: float

    def __init__(
        self,
        center: object,
        start: object,
        midpoint: object,
    ) -> None:
        center = point2(center, name="center")
        start_point = point2(start, name="start")
        midpoint_point = point2(midpoint, name="midpoint")
        radius = _radius2(center, start_point)
        midpoint_radius = _radius2(center, midpoint_point)
        if abs(midpoint_radius - radius) > 1e-9:
            raise ValueError(
                "Arc2 start and midpoint points must be the same distance from center"
            )
        start_rad = atan2(start_point[1] - center[1], start_point[0] - center[0])
        midpoint_rad = atan2(midpoint_point[1] - center[1], midpoint_point[0] - center[0])
        sweep_to_midpoint = _signed_angle_delta(start_rad, midpoint_rad)
        if sweep_to_midpoint == 0.0:
            raise ValueError("Arc2 start and midpoint points must differ")
        end_rad = start_rad + 2.0 * sweep_to_midpoint
        end_point = _point2_on_arc(center, radius, end_rad)

        object.__setattr__(self, "center", center)
        object.__setattr__(self, "start", start_point)
        object.__setattr__(self, "midpoint", midpoint_point)
        object.__setattr__(self, "end", end_point)
        object.__setattr__(self, "radius", radius)
        object.__setattr__(self, "start_rad", start_rad)
        object.__setattr__(self, "end_rad", end_rad)

    def _point(self, angle: float) -> Point2:
        return _point2_on_arc(self.center, self.radius, angle)

    def bounds(self) -> tuple[Point2, Point2]:
        points = [self._point(self.start_rad), self._point(self.end_rad)]
        for angle in (0.0, pi / 2.0, pi, 3.0 * pi / 2.0):
            if _angle_in_sweep(angle, self.start_rad, self.end_rad):
                points.append(self._point(angle))
        return (
            (min(point[0] for point in points), min(point[1] for point in points)),
            (max(point[0] for point in points), max(point[1] for point in points)),
        )

    @property
    def boundary(self) -> tuple[Point2, Point2]:
        return self.bounds()

    @property
    def length(self) -> float:
        return abs(self.end_rad - self.start_rad) * self.radius

    def points(self) -> tuple[Point2, ...]:
        return (self.start, self.end)

    def reverse(self) -> Arc2:
        return Arc2(self.center, self.end, self.midpoint)

    def discretize(
        self,
        *,
        tolerance: float,
        max_segment_length: float | None = None,
        min_segments: int = 1,
    ) -> Polyline2:
        tolerance = positive_tolerance(tolerance)
        min_segments = _min_segments(min_segments)

        sweep = self.end_rad - self.start_rad
        segment_count = _segment_count(
            radius=self.radius,
            sweep=sweep,
            tolerance=tolerance,
            max_segment_length=max_segment_length,
            min_segments=min_segments,
        )
        points = tuple(
            self._point(self.start_rad + sweep * index / segment_count)
            for index in range(segment_count + 1)
        )
        from cady.geometry.polyline import Polyline2

        return Polyline2(points)


@dataclass(frozen=True, slots=True, init=False)
class Arc3:
    """Circular 3D arc described by center, start, and arc midpoint."""

    center: Point3
    start: Point3
    midpoint: Point3
    end: Point3
    radius: float
    start_rad: float
    end_rad: float
    x_axis: Point3
    y_axis: Point3

    def __init__(
        self,
        center: object,
        start: object,
        midpoint: object,
    ) -> None:
        center = point3(center, name="center")
        start_point = point3(start, name="start")
        midpoint_point = point3(midpoint, name="midpoint")
        start_vector = sub3(start_point, center)
        midpoint_vector = sub3(midpoint_point, center)
        radius = positive(length3(start_vector), "radius")
        midpoint_radius = length3(midpoint_vector)
        if abs(midpoint_radius - radius) > 1e-9:
            raise ValueError(
                "Arc3 start and midpoint points must be the same distance from center"
            )
        x = scale3(start_vector, 1.0 / radius)
        y_component = sub3(midpoint_vector, scale3(x, dot3(midpoint_vector, x)))
        y_length = length3(y_component)
        if y_length == 0.0:
            raise ValueError("Arc3 center, start, and midpoint points must not be collinear")
        y = scale3(y_component, 1.0 / y_length)
        start_rad = 0.0
        midpoint_rad = atan2(dot3(midpoint_vector, y), dot3(midpoint_vector, x))
        sweep_to_midpoint = _signed_angle_delta(start_rad, midpoint_rad)
        if sweep_to_midpoint == 0.0:
            raise ValueError("Arc3 start and midpoint points must differ")
        end_rad = start_rad + 2.0 * sweep_to_midpoint
        end_point = _point3_on_arc(center, radius, end_rad, x, y)

        object.__setattr__(self, "center", center)
        object.__setattr__(self, "start", start_point)
        object.__setattr__(self, "midpoint", midpoint_point)
        object.__setattr__(self, "end", end_point)
        object.__setattr__(self, "radius", radius)
        object.__setattr__(self, "start_rad", start_rad)
        object.__setattr__(self, "end_rad", end_rad)
        object.__setattr__(self, "x_axis", x)
        object.__setattr__(self, "y_axis", y)

    def _point(self, angle: float) -> Point3:
        return _point3_on_arc(self.center, self.radius, angle, self.x_axis, self.y_axis)

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

    @property
    def length(self) -> float:
        return abs(self.end_rad - self.start_rad) * self.radius

    def points(self) -> tuple[Point3, Point3]:
        return (self.start, self.end)

    def reverse(self) -> Arc3:
        return Arc3(self.center, self.end, self.midpoint)

    def discretize(
        self,
        *,
        tolerance: float,
        max_segment_length: float | None = None,
        min_segments: int = 1,
    ) -> Polyline3:
        tolerance = positive_tolerance(tolerance)
        min_segments = _min_segments(min_segments)

        sweep = self.end_rad - self.start_rad
        segment_count = _segment_count(
            radius=self.radius,
            sweep=sweep,
            tolerance=tolerance,
            max_segment_length=max_segment_length,
            min_segments=min_segments,
        )
        points = tuple(
            self._point(self.start_rad + sweep * index / segment_count)
            for index in range(segment_count + 1)
        )
        from cady.geometry.polyline import Polyline3

        return Polyline3(points)


def _point2_on_arc(center: Point2, radius: float, angle: float) -> Point2:
    return (
        center[0] + radius * cos(angle),
        center[1] + radius * sin(angle),
    )


def _point3_on_arc(
    center: Point3,
    radius: float,
    angle: float,
    x_axis: Point3,
    y_axis: Point3,
) -> Point3:
    return add3(
        add3(center, scale3(x_axis, radius * cos(angle))),
        scale3(y_axis, radius * sin(angle)),
    )


def _radius2(center: Point2, point: Point2) -> float:
    return positive(
        ((point[0] - center[0]) ** 2 + (point[1] - center[1]) ** 2) ** 0.5,
        "radius",
    )


def _signed_angle_delta(start: float, end: float) -> float:
    return (end - start + pi) % (2.0 * pi) - pi


__all__ = ["Arc2", "Arc3"]
