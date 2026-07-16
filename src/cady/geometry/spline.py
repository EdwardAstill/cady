"""Cubic Bezier spline geometry in 2D and 3D."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias, cast

from cady.geometry.point import Point2 as Point2Value
from cady.geometry.point import Point3 as Point3Value
from cady.geometry.point import point2, point3
from cady.geometry.vector import vector2, vector3
from cady.operations.curve_sampling import (
    cubic_bezier_length2,
    cubic_bezier_length3,
    cubic_bezier_points2,
    cubic_bezier_points3,
    densify_points2,
    densify_points3,
    hermite_control_points2,
    hermite_control_points3,
)
from cady.operations.primitives import distance2
from cady.utils import positive, positive_tolerance

Point2: TypeAlias = Sequence[float]
Point3: TypeAlias = Sequence[float]

if TYPE_CHECKING:
    from cady.geometry.polyline import Polyline2, Polyline3


def _min_segments(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("min_segments must be an integer")
    if value < 1:
        raise ValueError("min_segments must be at least 1")
    return value


def _max_segment_length(value: float | None) -> float | None:
    if value is None:
        return None
    return positive(value, "max_segment_length")


@dataclass(frozen=True, slots=True, init=False)
class Spline2:
    """Cubic 2D spline made from points and tangent vectors."""

    control_points: tuple[Point2Value, ...]
    closed: bool = False

    def __init__(
        self,
        points: Iterable[object],
        vectors: Iterable[object] | bool | None = None,
        closed: bool = False,
    ) -> None:
        if isinstance(vectors, bool):
            closed = vectors
            vectors = None
        if vectors is None:
            control_points = tuple(point2(point) for point in points)
        else:
            source_points = tuple(point2(point) for point in points)
            source_vectors = tuple(vector2(vector) for vector in vectors)
            if closed and len(source_points) > 1 and source_points[0] == source_points[-1]:
                source_points = source_points[:-1]
                source_vectors = source_vectors[:-1]
            if len(source_points) < 2:
                raise ValueError("Spline2 requires at least two points")
            if len(source_vectors) != len(source_points):
                raise ValueError("Spline2 requires one tangent vector per point")
            control_points = tuple(
                point2(point)
                for point in hermite_control_points2(
                    source_points,
                    source_vectors,
                    closed=bool(closed),
                )
            )
        points = tuple(control_points)
        object.__setattr__(self, "control_points", points)
        object.__setattr__(self, "closed", bool(closed))
        if len(points) < 4 or (len(points) - 1) % 3 != 0:
            raise ValueError("Spline2 requires 3n+1 cubic Bezier control points")

    def bounds(self) -> tuple[Point2, Point2]:
        return (
            Point2Value(
                min(point[0] for point in self.control_points),
                min(point[1] for point in self.control_points),
            ),
            Point2Value(
                max(point[0] for point in self.control_points),
                max(point[1] for point in self.control_points),
            ),
        )

    @property
    def boundary(self) -> tuple[Point2, Point2]:
        return self.bounds()

    @property
    def length(self) -> float:
        length = sum(
            cubic_bezier_length2(
                cast(tuple[Point2, Point2, Point2, Point2], self.control_points[index : index + 4])
            )
            for index in range(0, len(self.control_points) - 1, 3)
        )
        if self.closed and self.control_points[0] != self.control_points[-1]:
            length += distance2(self.control_points[-1], self.control_points[0])
        return length

    def points(self) -> tuple[Point2Value, ...]:
        if self.closed and self.control_points[0] != self.control_points[-1]:
            return self.control_points + (self.control_points[0],)
        return self.control_points

    def discretize(
        self,
        *,
        tolerance: float,
        max_segment_length: float | None = None,
        min_segments: int = 1,
    ) -> Polyline2:
        tolerance = positive_tolerance(tolerance)
        max_segment_length = _max_segment_length(max_segment_length)
        min_segments = _min_segments(min_segments)

        points = cubic_bezier_points2(self.control_points, tolerance=tolerance)
        if self.closed and points[0] != points[-1]:
            points = (*points, points[0])
        points = densify_points2(
            points,
            max_segment_length=max_segment_length,
            min_segments=min_segments,
        )
        from cady.geometry.polyline import Polyline2

        return Polyline2(points, closed=self.closed)


@dataclass(frozen=True, slots=True, init=False)
class Spline3:
    """Cubic 3D spline made from points and tangent vectors."""

    control_points: tuple[Point3Value, ...]

    def __init__(
        self,
        points: Iterable[object],
        vectors: Iterable[object] | None = None,
    ) -> None:
        if vectors is None:
            control_points = tuple(point3(point) for point in points)
        else:
            source_points = tuple(point3(point) for point in points)
            source_vectors = tuple(vector3(vector) for vector in vectors)
            if len(source_points) < 2:
                raise ValueError("Spline3 requires at least two points")
            if len(source_vectors) != len(source_points):
                raise ValueError("Spline3 requires one tangent vector per point")
            control_points = tuple(
                point3(point)
                for point in hermite_control_points3(
                    source_points,
                    source_vectors,
                )
            )
        points = tuple(control_points)
        object.__setattr__(self, "control_points", points)
        if len(points) < 4 or (len(points) - 1) % 3 != 0:
            raise ValueError("Spline3 requires 3n+1 cubic Bezier control points")

    def bounds(self) -> tuple[Point3, Point3]:
        return (
            Point3Value(
                min(point[0] for point in self.control_points),
                min(point[1] for point in self.control_points),
                min(point[2] for point in self.control_points),
            ),
            Point3Value(
                max(point[0] for point in self.control_points),
                max(point[1] for point in self.control_points),
                max(point[2] for point in self.control_points),
            ),
        )

    @property
    def boundary(self) -> tuple[Point3, Point3]:
        return self.bounds()

    @property
    def length(self) -> float:
        return sum(
            cubic_bezier_length3(
                cast(tuple[Point3, Point3, Point3, Point3], self.control_points[index : index + 4])
            )
            for index in range(0, len(self.control_points) - 1, 3)
        )

    def points(self) -> tuple[Point3Value, ...]:
        return self.control_points

    def discretize(
        self,
        *,
        tolerance: float,
        max_segment_length: float | None = None,
        min_segments: int = 1,
    ) -> Polyline3:
        tolerance = positive_tolerance(tolerance)
        max_segment_length = _max_segment_length(max_segment_length)
        min_segments = _min_segments(min_segments)

        points = cubic_bezier_points3(self.control_points, tolerance=tolerance)
        from cady.geometry.polyline import Polyline3

        return Polyline3(
            densify_points3(
                points,
                max_segment_length=max_segment_length,
                min_segments=min_segments,
            )
        )


__all__ = ["Spline2", "Spline3"]
