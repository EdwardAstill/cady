"""Open and closed 2D and 3D polyline geometry."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from itertools import pairwise
from typing import TYPE_CHECKING, Protocol, TypeAlias, cast

from cady.errors import GeometryError
from cady.geometry.line import Line3
from cady.utils import loop_edges, positive_tolerance

Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]

if TYPE_CHECKING:
    from cady.geometry.mesh import Mesh2, Mesh3
    from cady.operations.arrays import PointArray2, PointArray3


FaceIndex = tuple[int, int, int]
EdgeIndex = tuple[int, int]


class Curve2(Protocol):
    """Common protocol for 2D curves that can be discretised on demand."""

    def bounds(self) -> tuple[Point2, Point2]: ...

    def points(self) -> tuple[Point2, ...]: ...

    def to_array(self, *, tolerance: float) -> PointArray2: ...


@dataclass(frozen=True, slots=True, init=False)
class Polyline2:
    """2D path made from straight segments, optionally closed."""

    vertices: tuple[Point2, ...]
    closed: bool = False

    def __init__(self, vertices: tuple[Point2, ...], closed: bool = False) -> None:
        vertices = tuple(vertices)
        closed = bool(closed)
        if closed and len(vertices) > 1 and vertices[0] == vertices[-1]:
            vertices = vertices[:-1]
        object.__setattr__(self, "vertices", vertices)
        object.__setattr__(self, "closed", closed)
        if closed:
            if len(vertices) < 3:
                raise ValueError("closed Polyline2 requires at least three vertices")
        elif len(vertices) < 2:
            raise ValueError("Polyline2 requires at least two vertices")

    def bounds(self) -> tuple[Point2, Point2]:
        return (
            (
                min(point[0] for point in self.vertices),
                min(point[1] for point in self.vertices),
            ),
            (
                max(point[0] for point in self.vertices),
                max(point[1] for point in self.vertices),
            ),
        )

    @property
    def boundary(self) -> tuple[Point2, Point2]:
        return self.bounds()

    def points(self) -> tuple[Point2, ...]:
        if self.closed:
            return self.vertices + (self.vertices[0],)
        return self.vertices

    def to_array(self, *, tolerance: float) -> PointArray2:
        positive_tolerance(tolerance)
        from cady.operations.arrays import as_points2

        return as_points2(self.vertices, name="vertices")

    def to_mesh(self, *, tolerance: float) -> Mesh2:
        if not self.closed:
            raise GeometryError("Polyline2 must be closed to create a mesh")
        tolerance = positive_tolerance(tolerance)
        from cady.geometry.mesh import Mesh2
        from cady.operations.triangulation import triangulate_polygon

        point_to_index = {point: index for index, point in enumerate(self.vertices)}
        triangles = triangulate_polygon(self.vertices, tolerance=tolerance)
        faces = tuple(
            (
                point_to_index[a],
                point_to_index[b],
                point_to_index[c],
            )
            for a, b, c in triangles
        )
        return Mesh2(self.vertices, faces, loop_edges(len(self.vertices)))


class Curve3(Protocol):
    """Common protocol for 3D curves that can be sampled to polylines."""

    def bounds(self) -> tuple[Point3, Point3]: ...

    def points(self) -> tuple[Point3, ...]: ...

    def to_array(self, *, tolerance: float) -> PointArray3: ...


def _is_curve3(value: object) -> bool:
    return (
        callable(getattr(value, "bounds", None))
        and callable(getattr(value, "points", None))
        and callable(getattr(value, "to_array", None))
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
            raise TypeError(
                "Polyline3 requires all items to be curves or all items to be vertices"
            )
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
                Line3(start, end)
                for start, end in pairwise(segment_vertices)
                if start != end
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
    ) -> Polyline3:
        polyline = cls(tuple(curves), closed=closed)
        if tolerance is None:
            return polyline
        return polyline.discretise(tolerance=tolerance)

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

    def discretise(self, *, tolerance: float) -> Polyline3:
        tolerance = positive_tolerance(tolerance)
        points: list[Point3] = []
        for curve in self.curves:
            array = curve.to_array(tolerance=tolerance)
            for x, y, z in array:
                point = (float(x), float(y), float(z))
                if not points or points[-1] != point:
                    points.append(point)
        return Polyline3(tuple(points), closed=self.closed)

    def discretize(self, *, tolerance: float) -> Polyline3:
        return self.discretise(tolerance=tolerance)

    def to_array(self, *, tolerance: float) -> PointArray3:
        tolerance = positive_tolerance(tolerance)
        points: list[Point3] = []
        for curve in self.curves:
            array = curve.to_array(tolerance=tolerance)
            for x, y, z in array:
                point = (float(x), float(y), float(z))
                if not points or points[-1] != point:
                    points.append(point)
        if self.closed and len(points) > 1 and points[0] == points[-1]:
            points.pop()

        from cady.operations.arrays import as_points3

        return as_points3(points, name="vertices")

    def to_mesh(self, *, tolerance: float) -> Mesh3:
        if not self.closed:
            raise GeometryError("Polyline3 must be closed to create a mesh")
        tolerance = positive_tolerance(tolerance)

        import numpy as np

        from cady.geometry.mesh import Mesh3
        from cady.operations.meshes import triangulate_loop
        from cady.operations.projections import fit_plane_svd, max_plane_deviation, project_loop

        vertex_arrays = [np.array(vertex, dtype=np.float64) for vertex in self.vertices]
        loop_points = np.array(vertex_arrays, dtype=np.float64)
        origin, normal = fit_plane_svd(loop_points)
        deviation = max_plane_deviation(loop_points, origin, normal)
        if deviation > tolerance:
            raise GeometryError(
                f"closed polyline is non-planar (max deviation {deviation:.3e} > "
                f"tolerance {tolerance:.3e})"
            )

        loop = list(range(len(self.vertices)))
        projected = project_loop(loop, vertex_arrays, origin, normal)
        faces = tuple(triangulate_loop(projected, tolerance))
        return Mesh3(self.vertices, faces, loop_edges(len(self.vertices)))


def _vertices_from_curves(curves: Iterable[Curve3]) -> tuple[Point3, ...]:
    points: list[Point3] = []
    for curve in curves:
        for point in curve.points():
            if not points or points[-1] != point:
                points.append(point)
    return tuple(points)


__all__ = [
    "Curve2",
    "Curve3",
    "Line3",
    "Polyline2",
    "Polyline3",
]
