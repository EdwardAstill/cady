from __future__ import annotations

from dataclasses import dataclass
from math import cos, isfinite, pi, sin
from typing import TYPE_CHECKING, Protocol

from cady.ops.curves2d import arc_points, circle_points, segments_for_circle
from cady.vec import Vec2, promote2

if TYPE_CHECKING:
    from cady.numeric import ArrayPolygon2, ArrayPolyline2


Point2Like = Vec2 | tuple[float, float]


class Curve2D(Protocol):
    def bounds(self) -> tuple[Vec2, Vec2]: ...

    def points(self) -> tuple[Vec2, ...]: ...

    def to_array(self, *, tolerance: float) -> object: ...


class ClosedCurve2D(Curve2D, Protocol):
    def to_array(self, *, tolerance: float) -> ArrayPolygon2: ...


def _finite(value: float, name: str) -> float:
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _positive(value: float, name: str) -> float:
    value = _finite(value, name)
    if value <= 0.0:
        raise ValueError(f"{name} must be positive")
    return value


def _positive_tolerance(tolerance: float) -> float:
    return _positive(tolerance, "tolerance")


def _bounds(points: tuple[Vec2, ...]) -> tuple[Vec2, Vec2]:
    if not points:
        raise ValueError("bounds require at least one point")
    return (
        Vec2(min(point.x for point in points), min(point.y for point in points)),
        Vec2(max(point.x for point in points), max(point.y for point in points)),
    )


def _point_tuples(points: tuple[Vec2, ...]) -> tuple[tuple[float, float], ...]:
    return tuple(point.tuple() for point in points)


def _polyline(points: tuple[Vec2, ...], *, closed: bool) -> ArrayPolyline2:
    from cady.numeric import ArrayPolyline2
    from cady.numeric.validation import as_points2

    return ArrayPolyline2(as_points2(_point_tuples(points), name="vertices"), closed=closed)


def _polygon(points: tuple[Vec2, ...]) -> ArrayPolygon2:
    from cady.numeric import ArrayPolygon2
    from cady.numeric.validation import as_points2

    return ArrayPolygon2(as_points2(_point_tuples(_dedupe_closed(points)), name="outer"))


def _dedupe_closed(points: tuple[Vec2, ...]) -> tuple[Vec2, ...]:
    if len(points) > 1 and points[0] == points[-1]:
        return points[:-1]
    return points


def _sample_count_for_ellipse(radius_x: float, radius_y: float, tolerance: float) -> int:
    return segments_for_circle(max(radius_x, radius_y), tolerance)


@dataclass(frozen=True, slots=True, init=False)
class Line2D:
    start: Vec2
    end: Vec2

    def __init__(self, start: Point2Like, end: Point2Like) -> None:
        start = promote2(start)
        end = promote2(end)
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        if start == end:
            raise ValueError("Line2D endpoints must differ")

    def bounds(self) -> tuple[Vec2, Vec2]:
        return _bounds((self.start, self.end))

    def points(self) -> tuple[Vec2, ...]:
        return (self.start, self.end)

    def to_array(self, *, tolerance: float) -> ArrayPolyline2:
        _positive_tolerance(tolerance)
        return _polyline(self.points(), closed=False)


@dataclass(frozen=True, slots=True, init=False)
class Arc2D:
    centre: Vec2
    radius: float
    start_rad: float
    end_rad: float

    def __init__(
        self,
        centre: Point2Like,
        radius: float,
        start_rad: float,
        end_rad: float,
    ) -> None:
        radius = _positive(radius, "radius")
        start_rad = _finite(start_rad, "start_rad")
        end_rad = _finite(end_rad, "end_rad")
        object.__setattr__(self, "centre", promote2(centre))
        object.__setattr__(self, "radius", radius)
        object.__setattr__(self, "start_rad", start_rad)
        object.__setattr__(self, "end_rad", end_rad)
        if start_rad == end_rad:
            raise ValueError("Arc2D start and end angles must differ")

    def _point(self, angle: float) -> Vec2:
        return Vec2(
            self.centre.x + self.radius * cos(angle),
            self.centre.y + self.radius * sin(angle),
        )

    def bounds(self) -> tuple[Vec2, Vec2]:
        points = [self._point(self.start_rad), self._point(self.end_rad)]
        start = self.start_rad % (2 * pi)
        sweep = (self.end_rad - self.start_rad) % (2 * pi)
        for angle in (0.0, pi / 2.0, pi, 3.0 * pi / 2.0):
            if (angle - start) % (2 * pi) <= sweep:
                points.append(self._point(angle))
        return _bounds(tuple(points))

    def points(self) -> tuple[Vec2, ...]:
        return (self._point(self.start_rad), self._point(self.end_rad))

    def to_array(self, *, tolerance: float) -> ArrayPolyline2:
        tolerance = _positive_tolerance(tolerance)
        points = tuple(
            Vec2(x, y)
            for x, y in arc_points(
                self.centre.tuple(),
                self.radius,
                self.start_rad,
                self.end_rad,
                tolerance=tolerance,
            )
        )
        return _polyline(points, closed=False)


@dataclass(frozen=True, slots=True, init=False)
class Spline2D:
    control_points: tuple[Vec2, ...]
    closed: bool = False

    def __init__(self, control_points: tuple[Point2Like, ...], closed: bool = False) -> None:
        points = tuple(promote2(point) for point in control_points)
        object.__setattr__(self, "control_points", points)
        object.__setattr__(self, "closed", bool(closed))
        if len(points) < 4 or (len(points) - 1) % 3 != 0:
            raise ValueError("Spline2D requires 3n+1 cubic Bezier control points")

    def bounds(self) -> tuple[Vec2, Vec2]:
        return _bounds(self.control_points)

    def points(self) -> tuple[Vec2, ...]:
        if self.closed and self.control_points[0] != self.control_points[-1]:
            return self.control_points + (self.control_points[0],)
        return self.control_points

    def to_array(self, *, tolerance: float) -> ArrayPolyline2:
        tolerance = _positive_tolerance(tolerance)
        from cady.numeric import ArrayBezierSpline2
        from cady.numeric.validation import as_points2

        spline = ArrayBezierSpline2(
            as_points2(_point_tuples(self.control_points), name="control_points"),
            closed=self.closed,
        )
        return spline.sample(tolerance=tolerance)


@dataclass(frozen=True, slots=True, init=False)
class Polyline2D:
    vertices: tuple[Vec2, ...]

    def __init__(self, vertices: tuple[Point2Like, ...]) -> None:
        vertices = tuple(promote2(point) for point in vertices)
        object.__setattr__(self, "vertices", vertices)
        if len(vertices) < 2:
            raise ValueError("Polyline2D requires at least two vertices")

    def bounds(self) -> tuple[Vec2, Vec2]:
        return _bounds(self.vertices)

    def points(self) -> tuple[Vec2, ...]:
        return self.vertices

    def to_array(self, *, tolerance: float) -> ArrayPolyline2:
        _positive_tolerance(tolerance)
        return _polyline(self.vertices, closed=False)


@dataclass(frozen=True, slots=True, init=False)
class Circle2D:
    centre: Vec2
    radius: float

    def __init__(self, centre: Point2Like, radius: float) -> None:
        object.__setattr__(self, "centre", promote2(centre))
        object.__setattr__(self, "radius", _positive(radius, "radius"))

    def bounds(self) -> tuple[Vec2, Vec2]:
        return (
            Vec2(self.centre.x - self.radius, self.centre.y - self.radius),
            Vec2(self.centre.x + self.radius, self.centre.y + self.radius),
        )

    def points(self) -> tuple[Vec2, ...]:
        point = Vec2(self.centre.x + self.radius, self.centre.y)
        return (point, point)

    def to_array(self, *, tolerance: float) -> ArrayPolygon2:
        tolerance = _positive_tolerance(tolerance)
        return _polygon(
            tuple(
                Vec2(x, y)
                for x, y in circle_points(
                    self.centre.tuple(),
                    self.radius,
                    tolerance=tolerance,
                )
            )
        )


@dataclass(frozen=True, slots=True, init=False)
class Ellipse2D:
    centre: Vec2
    radius_x: float
    radius_y: float
    rotation_rad: float = 0.0

    def __init__(
        self,
        centre: Point2Like,
        radius_x: float,
        radius_y: float,
        rotation_rad: float = 0.0,
    ) -> None:
        object.__setattr__(self, "centre", promote2(centre))
        object.__setattr__(self, "radius_x", _positive(radius_x, "radius_x"))
        object.__setattr__(self, "radius_y", _positive(radius_y, "radius_y"))
        object.__setattr__(self, "rotation_rad", _finite(rotation_rad, "rotation_rad"))

    def _sample_points(self, *, tolerance: float) -> tuple[Vec2, ...]:
        count = _sample_count_for_ellipse(self.radius_x, self.radius_y, tolerance)
        cr = cos(self.rotation_rad)
        sr = sin(self.rotation_rad)
        points: list[Vec2] = []
        for index in range(count):
            angle = 2.0 * pi * index / count
            x = self.radius_x * cos(angle)
            y = self.radius_y * sin(angle)
            points.append(Vec2(self.centre.x + x * cr - y * sr, self.centre.y + x * sr + y * cr))
        return tuple(points)

    def bounds(self) -> tuple[Vec2, Vec2]:
        cr = cos(self.rotation_rad)
        sr = sin(self.rotation_rad)
        half_width = ((self.radius_x * cr) ** 2 + (self.radius_y * sr) ** 2) ** 0.5
        half_height = ((self.radius_x * sr) ** 2 + (self.radius_y * cr) ** 2) ** 0.5
        return (
            Vec2(self.centre.x - half_width, self.centre.y - half_height),
            Vec2(self.centre.x + half_width, self.centre.y + half_height),
        )

    def points(self) -> tuple[Vec2, ...]:
        cr = cos(self.rotation_rad)
        sr = sin(self.rotation_rad)
        start = Vec2(self.centre.x + self.radius_x * cr, self.centre.y + self.radius_x * sr)
        return (start, start)

    def to_array(self, *, tolerance: float) -> ArrayPolygon2:
        tolerance = _positive_tolerance(tolerance)
        return _polygon(self._sample_points(tolerance=tolerance))


@dataclass(frozen=True, slots=True, init=False)
class ClosedPolyline2D:
    vertices: tuple[Vec2, ...]

    def __init__(self, vertices: tuple[Point2Like, ...]) -> None:
        vertices = _dedupe_closed(tuple(promote2(point) for point in vertices))
        object.__setattr__(self, "vertices", vertices)
        if len(vertices) < 3:
            raise ValueError("ClosedPolyline2D requires at least three vertices")

    def bounds(self) -> tuple[Vec2, Vec2]:
        return _bounds(self.vertices)

    def points(self) -> tuple[Vec2, ...]:
        return self.vertices + (self.vertices[0],)

    def to_array(self, *, tolerance: float) -> ArrayPolygon2:
        _positive_tolerance(tolerance)
        return _polygon(self.vertices)
