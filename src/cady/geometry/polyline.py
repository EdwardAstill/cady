"""Open and closed 2D and 3D polyline geometry."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from itertools import pairwise
from math import acos, degrees, dist, fsum, isfinite
from numbers import Real
from typing import TYPE_CHECKING, Protocol, TypeAlias, cast

import numpy as np
from numpy.typing import NDArray

from cady.errors import GeometryError
from cady.geometry.line import Line2, Line3
from cady.utils import positive_tolerance

Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]
PointArray2: TypeAlias = NDArray[np.float64]
PointArray3: TypeAlias = NDArray[np.float64]

if TYPE_CHECKING:
    from cady.geometry.mesh import Mesh2, Mesh3


FaceIndex = tuple[int, int, int]
EdgeIndex = tuple[int, int]


class Curve2(Protocol):
    """Common protocol for 2D curves that can be discretized on demand."""

    def bounds(self) -> tuple[Point2, Point2]: ...

    def points(self) -> tuple[Point2, ...]: ...


def _is_curve2(value: object) -> bool:
    return (
        callable(getattr(value, "bounds", None))
        and callable(getattr(value, "points", None))
    )


@dataclass(frozen=True, slots=True, init=False)
class Polyline2:
    """2D path made from straight segments, optionally closed."""

    curves: tuple[Curve2, ...]
    closed: bool = False

    def __init__(self, items: Iterable[Curve2 | Point2], closed: bool = False) -> None:
        items = tuple(items)
        if not items:
            raise ValueError("Polyline2 requires at least one curve or two vertices")

        closed = bool(closed)
        curve_flags = tuple(_is_curve2(item) for item in items)
        if all(curve_flags):
            curves = tuple(cast(Curve2, item) for item in items)
            if closed:
                vertices = _vertices2_from_curves(curves)
                if len(set(vertices)) < 3:
                    raise ValueError("closed Polyline2 requires at least three unique vertices")
                if vertices[0] != vertices[-1]:
                    curves = (*curves, Line2(vertices[-1], vertices[0]))
        elif any(curve_flags):
            raise TypeError("Polyline2 requires all items to be curves or all items to be vertices")
        else:
            vertices = tuple(cast(Point2, item) for item in items)
            if closed and len(vertices) > 1 and vertices[0] == vertices[-1]:
                vertices = vertices[:-1]
            if closed and len(set(vertices)) < 3:
                raise ValueError("closed Polyline2 requires at least three unique vertices")
            if len(vertices) < 2:
                raise ValueError("Polyline2 requires at least two vertices")
            segment_vertices = vertices + (vertices[0],) if closed else vertices
            curves = tuple(
                Line2(start, end) for start, end in pairwise(segment_vertices) if start != end
            )
            if not curves:
                raise ValueError("Polyline2 requires at least two distinct vertices")

        object.__setattr__(self, "curves", curves)
        object.__setattr__(self, "closed", closed)

    @classmethod
    def from_curves(
        cls,
        curves: Iterable[Curve2],
        *,
        closed: bool = False,
        tolerance: float | None = None,
        max_segment_length: float | None = None,
        min_segments: int = 1,
    ) -> Polyline2:
        polyline = cls(tuple(curves), closed=closed)
        if tolerance is None:
            return polyline
        return polyline.discretize(
            tolerance=tolerance,
            max_segment_length=max_segment_length,
            min_segments=min_segments,
        )

    @property
    def vertices(self) -> tuple[Point2, ...]:
        points = list(_vertices2_from_curves(self.curves))
        if self.closed and len(points) > 1 and points[0] == points[-1]:
            points.pop()
        return tuple(points)

    def bounds(self) -> tuple[Point2, Point2]:
        points = tuple(bound for curve in self.curves for bound in curve.bounds())
        return (
            (
                min(point[0] for point in points),
                min(point[1] for point in points),
            ),
            (
                max(point[0] for point in points),
                max(point[1] for point in points),
            ),
        )

    @property
    def boundary(self) -> tuple[Point2, Point2]:
        return self.bounds()

    @property
    def length(self) -> float:
        return sum(_curve_length(curve) for curve in self.curves)

    @property
    def start(self) -> Point2:
        return self.points()[0]

    @property
    def end(self) -> Point2:
        return self.points()[-1]

    @property
    def area(self) -> float:
        """Signed area of a closed polyline via the shoelace formula.

        Raises ``GeometryError`` when the polyline is not closed.
        The area is positive for counter-clockwise vertex order.
        """
        if not self.closed:
            raise GeometryError("Polyline2 must be closed to compute area")
        vertices = self.vertices
        if len(vertices) < 3:
            raise GeometryError("Polyline2 must have at least three vertices for area")
        return abs(
            fsum(
                vertices[i][0] * vertices[(i + 1) % len(vertices)][1]
                - vertices[(i + 1) % len(vertices)][0] * vertices[i][1]
                for i in range(len(vertices))
            )
            * 0.5
        )

    def points(self) -> tuple[Point2, ...]:
        if self.closed:
            return self.vertices + (self.vertices[0],)
        return self.vertices

    def reverse(self) -> Polyline2:
        return Polyline2(
            tuple(_reverse_curve2(curve) for curve in reversed(self.curves)),
            closed=self.closed,
        )

    def discontinuities(
        self,
        *,
        min_angle_degrees: float = 30.0,
        min_segment_length: float = 0.0,
    ) -> tuple[Point2, ...]:
        """Return vertices where adjacent segment directions turn sharply.

        The measured angle is the change in travel direction: a straight
        continuation is 0 degrees and a square corner is 90 degrees.
        """
        return _polyline2_discontinuities(
            self.vertices,
            closed=self.closed,
            min_angle_degrees=min_angle_degrees,
            min_segment_length=min_segment_length,
        )

    def discretize(
        self,
        *,
        tolerance: float,
        max_segment_length: float | None = None,
        min_segments: int = 1,
    ) -> Polyline2:
        tolerance = positive_tolerance(tolerance)
        points: list[Point2] = []
        for curve in self.curves:
            for point in _discretized_points2(
                curve,
                tolerance=tolerance,
                max_segment_length=max_segment_length,
                min_segments=min_segments,
            ):
                if not points or points[-1] != point:
                    points.append(point)
        return Polyline2(tuple(points), closed=self.closed)

    def to_array(self, *, tolerance: float) -> PointArray2:
        tolerance = positive_tolerance(tolerance)

        points: list[Point2] = []
        for curve in self.curves:
            if not isinstance(curve, Line2):
                raise GeometryError(
                    "Polyline2 contains curved segments; call discretize() before to_array()"
                )
            for point in curve.points():
                if not points or points[-1] != point:
                    points.append(point)
        if self.closed and len(points) > 1 and points[0] == points[-1]:
            points.pop()

        return np.array(points, dtype=np.float64, copy=True)

    def to_mesh(self, *, tolerance: float) -> Mesh2:
        if not self.closed:
            raise GeometryError("Polyline2 must be closed to create a mesh")
        tolerance = positive_tolerance(tolerance)
        from cady.operations.mesh.construction import closed_polyline_mesh2

        return closed_polyline_mesh2(self, tolerance=tolerance)


class Curve3(Protocol):
    """Common protocol for 3D curves that can be sampled to polylines."""

    def bounds(self) -> tuple[Point3, Point3]: ...

    def points(self) -> tuple[Point3, ...]: ...


def _is_curve3(value: object) -> bool:
    return (
        callable(getattr(value, "bounds", None))
        and callable(getattr(value, "points", None))
    )


@dataclass(frozen=True, slots=True, init=False)
class Polyline3:
    """3D curve path made from straight or curved segments, optionally closed.

    Passing vertices keeps the older straight-segment construction path.
    Passing curves stores the path as `Line3`, arc, spline, or other
    objects implementing `Curve3`.
    """

    curves: tuple[Curve3, ...]
    closed: bool = False

    def __init__(self, items: Iterable[Curve3 | Point3], closed: bool = False) -> None:
        items = tuple(items)
        if not items:
            raise ValueError("Polyline3 requires at least one curve or two vertices")

        closed = bool(closed)
        curve_flags = tuple(_is_curve3(item) for item in items)
        if all(curve_flags):
            curves = tuple(cast(Curve3, item) for item in items)
            if closed:
                vertices = _vertices_from_curves(curves)
                if len(set(vertices)) < 3:
                    raise ValueError("closed Polyline3 requires at least three unique vertices")
                if vertices[0] != vertices[-1]:
                    curves = (*curves, Line3(vertices[-1], vertices[0]))
        elif any(curve_flags):
            raise TypeError("Polyline3 requires all items to be curves or all items to be vertices")
        else:
            vertices = tuple(cast(Point3, item) for item in items)
            if closed and len(vertices) > 1 and vertices[0] == vertices[-1]:
                vertices = vertices[:-1]
            if closed and len(set(vertices)) < 3:
                raise ValueError("closed Polyline3 requires at least three unique vertices")
            if len(vertices) < 2:
                raise ValueError("Polyline3 requires at least two vertices")
            segment_vertices = vertices + (vertices[0],) if closed else vertices
            curves = tuple(
                Line3(start, end) for start, end in pairwise(segment_vertices) if start != end
            )
            if not curves:
                raise ValueError("Polyline3 requires at least two distinct vertices")

        object.__setattr__(self, "curves", curves)
        object.__setattr__(self, "closed", closed)

    @classmethod
    def from_curves(
        cls,
        curves: Iterable[Curve3],
        *,
        closed: bool = False,
        tolerance: float | None = None,
        max_segment_length: float | None = None,
        min_segments: int = 1,
    ) -> Polyline3:
        polyline = cls(tuple(curves), closed=closed)
        if tolerance is None:
            return polyline
        return polyline.discretize(
            tolerance=tolerance,
            max_segment_length=max_segment_length,
            min_segments=min_segments,
        )

    @property
    def vertices(self) -> tuple[Point3, ...]:
        points = list(_vertices_from_curves(self.curves))
        if self.closed and len(points) > 1 and points[0] == points[-1]:
            points.pop()
        return tuple(points)

    def bounds(self) -> tuple[Point3, Point3]:
        points = tuple(bound for curve in self.curves for bound in curve.bounds())
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
        return sum(_curve_length(curve) for curve in self.curves)

    @property
    def start(self) -> Point3:
        return self.points()[0]

    @property
    def end(self) -> Point3:
        return self.points()[-1]

    @property
    def area(self) -> float:
        """Area of a closed planar 3D polyline via Newell's method.

        Computes the polygon area from the magnitude of the summed
        cross products of consecutive vertex position vectors.

        Raises ``GeometryError`` when the polyline is not closed.
        """
        if not self.closed:
            raise GeometryError("Polyline3 must be closed to compute area")
        vertices = self.vertices
        if len(vertices) < 3:
            raise GeometryError("Polyline3 must have at least three vertices for area")
        n = len(vertices)
        cx = fsum(
            vertices[i][1] * vertices[(i + 1) % n][2] - vertices[i][2] * vertices[(i + 1) % n][1]
            for i in range(n)
        )
        cy = fsum(
            vertices[i][2] * vertices[(i + 1) % n][0] - vertices[i][0] * vertices[(i + 1) % n][2]
            for i in range(n)
        )
        cz = fsum(
            vertices[i][0] * vertices[(i + 1) % n][1] - vertices[i][1] * vertices[(i + 1) % n][0]
            for i in range(n)
        )
        return 0.5 * (cx * cx + cy * cy + cz * cz) ** 0.5

    def points(self) -> tuple[Point3, ...]:
        if self.closed:
            return self.vertices + (self.vertices[0],)
        return self.vertices

    def reverse(self) -> Polyline3:
        return Polyline3(
            tuple(_reverse_curve3(curve) for curve in reversed(self.curves)),
            closed=self.closed,
        )

    def discontinuities(
        self,
        *,
        min_angle_degrees: float = 30.0,
        min_segment_length: float = 0.0,
    ) -> tuple[Point3, ...]:
        """Return vertices where adjacent segment directions turn sharply.

        The measured angle is the change in travel direction: a straight
        continuation is 0 degrees and a square corner is 90 degrees.
        """
        return _polyline3_discontinuities(
            self.vertices,
            closed=self.closed,
            min_angle_degrees=min_angle_degrees,
            min_segment_length=min_segment_length,
        )

    def add(self, curve: Curve3) -> Polyline3:
        if self.closed:
            raise GeometryError("cannot add curves to a closed Polyline3")
        if not _is_curve3(curve):
            raise TypeError("Polyline3.add requires a Curve3")
        return Polyline3((*self.curves, curve))

    def discretize(
        self,
        *,
        tolerance: float,
        max_segment_length: float | None = None,
        min_segments: int = 1,
    ) -> Polyline3:
        tolerance = positive_tolerance(tolerance)
        points: list[Point3] = []
        for curve in self.curves:
            for point in _discretized_points3(
                curve,
                tolerance=tolerance,
                max_segment_length=max_segment_length,
                min_segments=min_segments,
            ):
                if not points or points[-1] != point:
                    points.append(point)
        return Polyline3(tuple(points), closed=self.closed)

    def to_array(self, *, tolerance: float) -> PointArray3:
        tolerance = positive_tolerance(tolerance)
        points: list[Point3] = []
        for curve in self.curves:
            if not isinstance(curve, Line3):
                raise GeometryError(
                    "Polyline3 contains curved segments; call discretize() before to_array()"
                )
            for point in curve.points():
                if not points or points[-1] != point:
                    points.append(point)
        if self.closed and len(points) > 1 and points[0] == points[-1]:
            points.pop()

        return np.array(points, dtype=np.float64, copy=True)

    def to_mesh(self, *, tolerance: float) -> Mesh3:
        if not self.closed:
            raise GeometryError("Polyline3 must be closed to create a mesh")
        tolerance = positive_tolerance(tolerance)

        from cady.operations.mesh.construction import closed_polyline_mesh3

        try:
            return closed_polyline_mesh3(self, tolerance=tolerance)
        except ValueError as exc:
            if "non-planar" in str(exc):
                raise GeometryError(str(exc)) from exc
            raise


def _vertices2_from_curves(curves: Iterable[Curve2]) -> tuple[Point2, ...]:
    points: list[Point2] = []
    for curve in curves:
        for point in curve.points():
            if not points or points[-1] != point:
                points.append(point)
    return tuple(points)


def _vertices_from_curves(curves: Iterable[Curve3]) -> tuple[Point3, ...]:
    points: list[Point3] = []
    for curve in curves:
        for point in curve.points():
            if not points or points[-1] != point:
                points.append(point)
    return tuple(points)


def _curve_length(curve: object) -> float:
    value = getattr(curve, "length", None)
    if not isinstance(value, Real):
        raise TypeError(f"{type(curve).__name__} does not expose an exact length")
    return float(value)


def _reverse_curve2(curve: Curve2) -> Curve2:
    if isinstance(curve, Line2):
        return Line2(curve.end, curve.start)

    reverse = getattr(curve, "reverse", None)
    if callable(reverse):
        reversed_curve = reverse()
        if _is_curve2(reversed_curve):
            return cast(Curve2, reversed_curve)

    from cady.geometry.arc import Arc2
    from cady.geometry.spline import Spline2

    if isinstance(curve, Arc2):
        return Arc2(curve.centre, curve.radius, curve.end_rad, curve.start_rad)
    if isinstance(curve, Spline2):
        return Spline2(tuple(reversed(curve.control_points)), closed=curve.closed)
    raise GeometryError(f"{type(curve).__name__} cannot be reversed")


def _reverse_curve3(curve: Curve3) -> Curve3:
    if isinstance(curve, Line3):
        return Line3(curve.end, curve.start)

    reverse = getattr(curve, "reverse", None)
    if callable(reverse):
        reversed_curve = reverse()
        if _is_curve3(reversed_curve):
            return cast(Curve3, reversed_curve)

    from cady.geometry.arc import Arc3
    from cady.geometry.spline import Spline3

    if isinstance(curve, Arc3):
        return Arc3(
            curve.centre,
            curve.radius,
            curve.end_rad,
            curve.start_rad,
            x_axis=curve.x_axis,
            y_axis=curve.y_axis,
        )
    if isinstance(curve, Spline3):
        return Spline3(tuple(reversed(curve.control_points)))
    raise GeometryError(f"{type(curve).__name__} cannot be reversed")


def _polyline2_discontinuities(
    points: tuple[Point2, ...],
    *,
    closed: bool,
    min_angle_degrees: float,
    min_segment_length: float,
) -> tuple[Point2, ...]:
    min_angle = _validated_min_angle_degrees(min_angle_degrees)
    min_length = _validated_min_segment_length(min_segment_length)
    if len(points) < 3:
        return ()

    discontinuities: list[Point2] = []
    if closed:
        point_triples = (
            (
                points[(index - 1) % len(points)],
                points[index],
                points[(index + 1) % len(points)],
            )
            for index in range(len(points))
        )
    else:
        point_triples = (
            (points[index - 1], points[index], points[index + 1])
            for index in range(1, len(points) - 1)
        )

    for previous, current, following in point_triples:
        angle = _turn_angle_degrees2(
            previous,
            current,
            following,
            min_segment_length=min_length,
        )
        if angle is not None and angle >= min_angle:
            discontinuities.append(current)
    return tuple(discontinuities)


def _polyline3_discontinuities(
    points: tuple[Point3, ...],
    *,
    closed: bool,
    min_angle_degrees: float,
    min_segment_length: float,
) -> tuple[Point3, ...]:
    min_angle = _validated_min_angle_degrees(min_angle_degrees)
    min_length = _validated_min_segment_length(min_segment_length)
    if len(points) < 3:
        return ()

    discontinuities: list[Point3] = []
    if closed:
        point_triples = (
            (
                points[(index - 1) % len(points)],
                points[index],
                points[(index + 1) % len(points)],
            )
            for index in range(len(points))
        )
    else:
        point_triples = (
            (points[index - 1], points[index], points[index + 1])
            for index in range(1, len(points) - 1)
        )

    for previous, current, following in point_triples:
        angle = _turn_angle_degrees3(
            previous,
            current,
            following,
            min_segment_length=min_length,
        )
        if angle is not None and angle >= min_angle:
            discontinuities.append(current)
    return tuple(discontinuities)


def _turn_angle_degrees2(
    previous: Point2,
    current: Point2,
    following: Point2,
    *,
    min_segment_length: float,
) -> float | None:
    incoming = (current[0] - previous[0], current[1] - previous[1])
    outgoing = (following[0] - current[0], following[1] - current[1])
    incoming_length = dist(previous, current)
    outgoing_length = dist(current, following)
    if incoming_length <= min_segment_length or outgoing_length <= min_segment_length:
        return None
    dot_product = incoming[0] * outgoing[0] + incoming[1] * outgoing[1]
    return _angle_degrees(dot_product, incoming_length, outgoing_length)


def _turn_angle_degrees3(
    previous: Point3,
    current: Point3,
    following: Point3,
    *,
    min_segment_length: float,
) -> float | None:
    incoming = (
        current[0] - previous[0],
        current[1] - previous[1],
        current[2] - previous[2],
    )
    outgoing = (
        following[0] - current[0],
        following[1] - current[1],
        following[2] - current[2],
    )
    incoming_length = dist(previous, current)
    outgoing_length = dist(current, following)
    if incoming_length <= min_segment_length or outgoing_length <= min_segment_length:
        return None
    dot_product = (
        incoming[0] * outgoing[0]
        + incoming[1] * outgoing[1]
        + incoming[2] * outgoing[2]
    )
    return _angle_degrees(dot_product, incoming_length, outgoing_length)


def _angle_degrees(dot_product: float, first_length: float, second_length: float) -> float:
    cosine = dot_product / (first_length * second_length)
    return degrees(acos(max(-1.0, min(1.0, cosine))))


def _validated_min_angle_degrees(value: float) -> float:
    angle = float(value)
    if not isfinite(angle) or angle <= 0.0 or angle > 180.0:
        raise ValueError("min_angle_degrees must be greater than 0 and at most 180")
    return angle


def _validated_min_segment_length(value: float) -> float:
    length = float(value)
    if not isfinite(length) or length < 0.0:
        raise ValueError("min_segment_length must be finite and non-negative")
    return length


def _discretized_points2(
    curve: Curve2,
    *,
    tolerance: float,
    max_segment_length: float | None,
    min_segments: int,
) -> tuple[Point2, ...]:
    if isinstance(curve, Line2):
        return curve.points()
    discretize = getattr(curve, "discretize", None)
    if not callable(discretize):
        raise TypeError(f"{type(curve).__name__} does not provide discretize(tolerance=...)")
    polyline = discretize(
        tolerance=tolerance,
        max_segment_length=max_segment_length,
        min_segments=min_segments,
    )
    return tuple(cast(Polyline2, polyline).points())


def _discretized_points3(
    curve: Curve3,
    *,
    tolerance: float,
    max_segment_length: float | None,
    min_segments: int,
) -> tuple[Point3, ...]:
    if isinstance(curve, Line3):
        return curve.points()
    discretize = getattr(curve, "discretize", None)
    if not callable(discretize):
        raise TypeError(f"{type(curve).__name__} does not provide discretize(tolerance=...)")
    polyline = discretize(
        tolerance=tolerance,
        max_segment_length=max_segment_length,
        min_segments=min_segments,
    )
    return tuple(cast(Polyline3, polyline).points())


__all__ = [
    "Curve2",
    "Curve3",
    "Line2",
    "Line3",
    "Polyline2",
    "Polyline3",
]
