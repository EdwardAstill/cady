"""Open and closed 2D and 3D polyline geometry."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from itertools import pairwise
from math import fsum
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
        from cady.operations.meshing import closed_polyline_mesh2

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

        from cady.operations.meshing import closed_polyline_mesh3

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
