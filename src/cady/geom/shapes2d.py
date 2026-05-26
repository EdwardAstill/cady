from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from itertools import pairwise
from math import atan2, cos, pi, sin

from cady.geom.base import Shape2D
from cady.geom.vec import Vec2, promote2


def _bounds(points: tuple[Vec2, ...]) -> tuple[Vec2, Vec2]:
    return (
        Vec2(min(p.x for p in points), min(p.y for p in points)),
        Vec2(max(p.x for p in points), max(p.y for p in points)),
    )


def _same(a: Vec2, b: Vec2, tol: float = 1e-9) -> bool:
    return (a - b).length() <= tol


@dataclass(frozen=True, slots=True)
class Line(Shape2D):
    a: Vec2
    b: Vec2
    closed: bool = False
    inner_loops: tuple[Shape2D, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "a", promote2(self.a))
        object.__setattr__(self, "b", promote2(self.b))
        if self.a == self.b:
            raise ValueError("Line endpoints must differ")
        if self.inner_loops:
            raise ValueError("open Line cannot carry holes")

    def bounds(self) -> tuple[Vec2, Vec2]:
        return _bounds((self.a, self.b))

    def points(self) -> tuple[Vec2, ...]:
        return (self.a, self.b)

    def close(self) -> Shape2D:
        return Path((self, Line(self.b, self.a)), closed=True)

    def _transform2(self, fn: Callable[[Vec2], Vec2]) -> Shape2D:
        return replace(self, a=fn(self.a), b=fn(self.b))


@dataclass(frozen=True, slots=True)
class Arc(Shape2D):
    centre: Vec2
    radius: float
    start_rad: float
    end_rad: float
    closed: bool = False
    inner_loops: tuple[Shape2D, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "centre", promote2(self.centre))
        object.__setattr__(self, "radius", float(self.radius))
        object.__setattr__(self, "start_rad", float(self.start_rad))
        object.__setattr__(self, "end_rad", float(self.end_rad))
        if self.radius <= 0:
            raise ValueError("Arc radius must be positive")
        if self.start_rad == self.end_rad:
            raise ValueError("Arc start and end angles must differ")
        if self.inner_loops:
            raise ValueError("open Arc cannot carry holes")

    def _point(self, angle: float) -> Vec2:
        return Vec2(
            self.centre.x + self.radius * cos(angle), self.centre.y + self.radius * sin(angle)
        )

    def bounds(self) -> tuple[Vec2, Vec2]:
        pts = [self._point(self.start_rad), self._point(self.end_rad)]
        start = self.start_rad % (2 * pi)
        end = self.end_rad % (2 * pi)
        sweep = (end - start) % (2 * pi)
        for angle in (0.0, pi / 2, pi, 3 * pi / 2):
            rel = (angle - start) % (2 * pi)
            if rel <= sweep:
                pts.append(self._point(angle))
        return _bounds(tuple(pts))

    def points(self) -> tuple[Vec2, ...]:
        return (self._point(self.start_rad), self._point(self.end_rad))

    def close(self) -> Shape2D:
        start, end = self.points()
        return Path((self, Line(end, start)), closed=True)

    def _transform2(self, fn: Callable[[Vec2], Vec2]) -> Shape2D:
        start, end = (fn(p) for p in self.points())
        centre = fn(self.centre)
        radius = (start - centre).length()
        return Arc(
            centre,
            radius,
            atan2(start.y - centre.y, start.x - centre.x),
            atan2(end.y - centre.y, end.x - centre.x),
        )


@dataclass(frozen=True, slots=True)
class Circle(Shape2D):
    centre: Vec2
    radius: float
    closed: bool = True
    inner_loops: tuple[Shape2D, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "centre", promote2(self.centre))
        object.__setattr__(self, "radius", float(self.radius))
        object.__setattr__(self, "closed", True)
        if self.radius <= 0:
            raise ValueError("Circle radius must be positive")

    def bounds(self) -> tuple[Vec2, Vec2]:
        return (
            Vec2(self.centre.x - self.radius, self.centre.y - self.radius),
            Vec2(self.centre.x + self.radius, self.centre.y + self.radius),
        )

    def points(self) -> tuple[Vec2, ...]:
        p = Vec2(self.centre.x + self.radius, self.centre.y)
        return (p, p)

    def close(self) -> Shape2D:
        return self

    def _transform2(self, fn: Callable[[Vec2], Vec2]) -> Shape2D:
        centre = fn(self.centre)
        edge = fn(Vec2(self.centre.x + self.radius, self.centre.y))
        loops = tuple(loop._transform2(fn) for loop in self.inner_loops)
        return Circle(centre, (edge - centre).length(), inner_loops=loops)


@dataclass(frozen=True, slots=True)
class Rectangle(Shape2D):
    origin: Vec2
    size: Vec2
    closed: bool = True
    inner_loops: tuple[Shape2D, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "origin", promote2(self.origin))
        object.__setattr__(self, "size", promote2(self.size))
        object.__setattr__(self, "closed", True)
        if self.size.x == 0 or self.size.y == 0:
            raise ValueError("Rectangle size components must be non-zero")

    def corners(self) -> tuple[Vec2, Vec2, Vec2, Vec2]:
        x0, y0 = self.origin.x, self.origin.y
        x1, y1 = x0 + self.size.x, y0 + self.size.y
        return (Vec2(x0, y0), Vec2(x1, y0), Vec2(x1, y1), Vec2(x0, y1))

    def bounds(self) -> tuple[Vec2, Vec2]:
        return _bounds(self.corners())

    def points(self) -> tuple[Vec2, ...]:
        return self.corners() + (self.corners()[0],)

    def close(self) -> Shape2D:
        return self

    def _transform2(self, fn: Callable[[Vec2], Vec2]) -> Shape2D:
        pts = tuple(fn(p) for p in self.corners())
        loops = tuple(loop._transform2(fn) for loop in self.inner_loops)
        if _same(pts[1] - pts[0] + pts[3], pts[2]):
            return Rectangle(
                pts[0],
                Vec2((pts[1] - pts[0]).length(), (pts[3] - pts[0]).length()),
                inner_loops=loops,
            )
        return Polyline(pts, closed=True, inner_loops=loops)


@dataclass(frozen=True, slots=True)
class Polyline(Shape2D):
    vertices: tuple[Vec2, ...]
    closed: bool = False
    inner_loops: tuple[Shape2D, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "vertices", tuple(promote2(p) for p in self.vertices))
        if not self.vertices:
            raise ValueError("Polyline requires at least one point")
        if self.closed and len(self.vertices) < 3:
            raise ValueError("closed Polyline requires at least three points")
        if self.inner_loops and not self.closed:
            raise ValueError("open Polyline cannot carry holes")

    def bounds(self) -> tuple[Vec2, Vec2]:
        return _bounds(self.vertices)

    def points(self) -> tuple[Vec2, ...]:
        if self.closed and self.vertices[0] != self.vertices[-1]:
            return self.vertices + (self.vertices[0],)
        return self.vertices

    def close(self) -> Shape2D:
        if len(self.vertices) < 3:
            raise ValueError("cannot close Polyline with fewer than three points")
        return replace(self, closed=True)

    def _transform2(self, fn: Callable[[Vec2], Vec2]) -> Shape2D:
        loops = tuple(loop._transform2(fn) for loop in self.inner_loops)
        return replace(self, vertices=tuple(fn(p) for p in self.vertices), inner_loops=loops)


@dataclass(frozen=True, slots=True)
class Spline(Shape2D):
    control_points: tuple[Vec2, ...]
    closed: bool = False
    inner_loops: tuple[Shape2D, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "control_points", tuple(promote2(p) for p in self.control_points))
        if len(self.control_points) < 4 or (len(self.control_points) - 1) % 3 != 0:
            raise ValueError("Spline requires 3n+1 cubic Bezier control points")
        if self.inner_loops and not self.closed:
            raise ValueError("open Spline cannot carry holes")

    def bounds(self) -> tuple[Vec2, Vec2]:
        return _bounds(self.control_points)

    def points(self) -> tuple[Vec2, ...]:
        if self.closed and self.control_points[0] != self.control_points[-1]:
            return self.control_points + (self.control_points[0],)
        return self.control_points

    def close(self) -> Shape2D:
        return replace(self, closed=True)

    def _transform2(self, fn: Callable[[Vec2], Vec2]) -> Shape2D:
        loops = tuple(loop._transform2(fn) for loop in self.inner_loops)
        return replace(
            self, control_points=tuple(fn(p) for p in self.control_points), inner_loops=loops
        )


@dataclass(frozen=True, slots=True)
class Path(Shape2D):
    segments: tuple[Shape2D, ...]
    closed: bool = False
    inner_loops: tuple[Shape2D, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.segments:
            raise ValueError("Path requires at least one segment")
        for segment in self.segments:
            if segment.closed:
                raise ValueError("Path segments must be open Shape2D values")
        for left, right in pairwise(self.segments):
            if not _same(left.points()[-1], right.points()[0]):
                raise ValueError("Path segments must be head-to-tail")
        if self.inner_loops and not self.closed:
            raise ValueError("open Path cannot carry holes")

    @classmethod
    def from_shapes(cls, left: Shape2D, right: Shape2D) -> Path:
        segments = (left.segments if isinstance(left, Path) else (left,)) + (
            right.segments if isinstance(right, Path) else (right,)
        )
        return cls(segments)

    def bounds(self) -> tuple[Vec2, Vec2]:
        pts = tuple(p for segment in self.segments for p in segment.points())
        return _bounds(pts)

    def points(self) -> tuple[Vec2, ...]:
        pts: list[Vec2] = [self.segments[0].points()[0]]
        for segment in self.segments:
            pts.extend(segment.points()[1:])
        if self.closed and pts[0] != pts[-1]:
            pts.append(pts[0])
        return tuple(pts)

    def close(self) -> Shape2D:
        first = self.points()[0]
        last = self.points()[-1]
        segments = self.segments if _same(first, last) else self.segments + (Line(last, first),)
        return replace(self, segments=segments, closed=True)

    def _transform2(self, fn: Callable[[Vec2], Vec2]) -> Shape2D:
        loops = tuple(loop._transform2(fn) for loop in self.inner_loops)
        return replace(
            self,
            segments=tuple(segment._transform2(fn) for segment in self.segments),
            inner_loops=loops,
        )
