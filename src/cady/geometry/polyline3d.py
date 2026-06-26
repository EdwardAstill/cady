from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from itertools import pairwise
from math import atan2, ceil, cos, pi, sin
from typing import TYPE_CHECKING, Protocol, cast

from cady.errors import GeometryError
from cady.operations.sampling2d import segments_for_circle
from cady.utils import finite, loop_edges, positive, positive_tolerance
from cady.vec import Vec3, promote3

if TYPE_CHECKING:
    from cady.geometry.mesh3d import Mesh3D
    from cady.operations.arrays3d import ArrayPolyline3


Point3Like = Vec3 | tuple[float, float, float]
FaceIndex = tuple[int, int, int]
EdgeIndex = tuple[int, int]


class Curve3D(Protocol):
    def bounds(self) -> tuple[Vec3, Vec3]: ...

    def points(self) -> tuple[Vec3, ...]: ...

    def to_array(self, *, tolerance: float) -> ArrayPolyline3: ...


def _bounds(points: tuple[Vec3, ...]) -> tuple[Vec3, Vec3]:
    if not points:
        raise ValueError("bounds require at least one point")
    return (
        Vec3(
            min(point.x for point in points),
            min(point.y for point in points),
            min(point.z for point in points),
        ),
        Vec3(
            max(point.x for point in points),
            max(point.y for point in points),
            max(point.z for point in points),
        ),
    )


def _dedupe_closed(vertices: tuple[Vec3, ...]) -> tuple[Vec3, ...]:
    if len(vertices) > 1 and vertices[0] == vertices[-1]:
        return vertices[:-1]
    return vertices


def _unique_vertex_count(vertices: tuple[Vec3, ...]) -> int:
    return len({vertex.tuple() for vertex in vertices})


def _polyline3(points: tuple[Vec3, ...]) -> ArrayPolyline3:
    import numpy as np

    from cady.operations.arrays3d import ArrayPolyline3

    return ArrayPolyline3(
        np.array([point.tuple() for point in points], dtype=np.float64)
    )


def _append_unique_point(points: list[Vec3], point: Vec3) -> None:
    if not points or points[-1] != point:
        points.append(point)


def _path_points(curves: tuple[Curve3D, ...]) -> tuple[Vec3, ...]:
    points: list[Vec3] = []
    for curve in curves:
        for point in curve.points():
            _append_unique_point(points, point)
    return tuple(points)


def _discretised_points(
    curves: tuple[Curve3D, ...],
    *,
    tolerance: float,
) -> tuple[Vec3, ...]:
    tolerance = positive_tolerance(tolerance)
    points: list[Vec3] = []
    for curve in curves:
        array = curve.to_array(tolerance=tolerance)
        for x, y, z in array.vertices:
            _append_unique_point(points, Vec3(float(x), float(y), float(z)))
    return tuple(points)


def _is_curve3d(value: object) -> bool:
    return (
        callable(getattr(value, "bounds", None))
        and callable(getattr(value, "points", None))
        and callable(getattr(value, "to_array", None))
    )


def _line_curves_from_vertices(vertices: tuple[Vec3, ...]) -> tuple[Curve3D, ...]:
    curves = tuple(Line3D(start, end) for start, end in pairwise(vertices) if start != end)
    if not curves:
        raise ValueError("Polyline3D requires at least two distinct vertices")
    return curves


def _unit_axis(axis: Point3Like, name: str) -> Vec3:
    vector = promote3(axis)
    length = vector.length()
    if length == 0.0:
        raise ValueError(f"{name} must not be zero length")
    return vector * (1.0 / length)


def _angle_in_sweep(angle: float, start_rad: float, end_rad: float) -> bool:
    sweep = end_rad - start_rad
    if abs(sweep) >= 2.0 * pi:
        return True
    if sweep > 0.0:
        return (angle - start_rad) % (2.0 * pi) <= sweep
    return (start_rad - angle) % (2.0 * pi) <= -sweep


@dataclass(frozen=True, slots=True, init=False)
class Line3D:
    """Straight 3D curve segment."""

    start: Vec3
    end: Vec3

    def __init__(self, start: Point3Like, end: Point3Like) -> None:
        start = promote3(start)
        end = promote3(end)
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        if start == end:
            raise ValueError("Line3D endpoints must differ")

    def bounds(self) -> tuple[Vec3, Vec3]:
        return _bounds((self.start, self.end))

    def points(self) -> tuple[Vec3, Vec3]:
        return (self.start, self.end)

    def to_array(self, *, tolerance: float) -> ArrayPolyline3:
        positive_tolerance(tolerance)
        return _polyline3(self.points())


@dataclass(frozen=True, slots=True, init=False)
class Arc3D:
    """Circular 3D arc in the plane spanned by two perpendicular axes."""

    centre: Vec3
    radius: float
    start_rad: float
    end_rad: float
    x_axis: Vec3
    y_axis: Vec3

    def __init__(
        self,
        centre: Point3Like,
        radius: float,
        start_rad: float,
        end_rad: float,
        *,
        x_axis: Point3Like = (1.0, 0.0, 0.0),
        y_axis: Point3Like = (0.0, 1.0, 0.0),
    ) -> None:
        radius = positive(radius, "radius")
        start_rad = finite(start_rad, "start_rad")
        end_rad = finite(end_rad, "end_rad")
        if start_rad == end_rad:
            raise ValueError("Arc3D start and end angles must differ")

        x = _unit_axis(x_axis, "x_axis")
        y = _unit_axis(y_axis, "y_axis")
        if abs(x.dot(y)) > 1e-9:
            raise ValueError("Arc3D x_axis and y_axis must be perpendicular")

        object.__setattr__(self, "centre", promote3(centre))
        object.__setattr__(self, "radius", radius)
        object.__setattr__(self, "start_rad", start_rad)
        object.__setattr__(self, "end_rad", end_rad)
        object.__setattr__(self, "x_axis", x)
        object.__setattr__(self, "y_axis", y)

    def _point(self, angle: float) -> Vec3:
        return (
            self.centre
            + self.x_axis * (self.radius * cos(angle))
            + self.y_axis * (self.radius * sin(angle))
        )

    def bounds(self) -> tuple[Vec3, Vec3]:
        candidate_angles = [self.start_rad, self.end_rad]
        axis_pairs = (
            (self.x_axis.x, self.y_axis.x),
            (self.x_axis.y, self.y_axis.y),
            (self.x_axis.z, self.y_axis.z),
        )
        for x_component, y_component in axis_pairs:
            angle = atan2(y_component, x_component)
            for candidate in (angle, angle + pi):
                if _angle_in_sweep(candidate, self.start_rad, self.end_rad):
                    candidate_angles.append(candidate)
        return _bounds(tuple(self._point(angle) for angle in candidate_angles))

    def points(self) -> tuple[Vec3, Vec3]:
        return (self._point(self.start_rad), self._point(self.end_rad))

    def to_array(self, *, tolerance: float) -> ArrayPolyline3:
        tolerance = positive_tolerance(tolerance)
        import numpy as np

        from cady.operations.arrays3d import ArrayPolyline3

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
        return ArrayPolyline3(
            np.array([point.tuple() for point in points], dtype=np.float64)
        )


@dataclass(frozen=True, slots=True, init=False)
class Spline3D:
    """Cubic Bezier spline made from 3n+1 3D control points."""

    control_points: tuple[Vec3, ...]

    def __init__(self, control_points: Iterable[Point3Like]) -> None:
        points = tuple(promote3(point) for point in control_points)
        object.__setattr__(self, "control_points", points)
        if len(points) < 4 or (len(points) - 1) % 3 != 0:
            raise ValueError("Spline3D requires 3n+1 cubic Bezier control points")

    def bounds(self) -> tuple[Vec3, Vec3]:
        return _bounds(self.control_points)

    def points(self) -> tuple[Vec3, ...]:
        return self.control_points

    def to_array(self, *, tolerance: float) -> ArrayPolyline3:
        tolerance = positive_tolerance(tolerance)
        points: list[Vec3] = []
        for index in range(0, len(self.control_points) - 1, 3):
            segment = self.control_points[index : index + 4]
            _append_cubic_points(
                points,
                segment[0],
                segment[1],
                segment[2],
                segment[3],
                tolerance=tolerance,
                depth=0,
            )
        return _polyline3(tuple(points))


def _append_cubic_points(
    points: list[Vec3],
    p0: Vec3,
    p1: Vec3,
    p2: Vec3,
    p3: Vec3,
    *,
    tolerance: float,
    depth: int,
) -> None:
    if depth >= 16 or _cubic_is_flat_enough(p0, p1, p2, p3, tolerance=tolerance):
        _append_unique_point(points, p0)
        _append_unique_point(points, p3)
        return

    p01 = _midpoint(p0, p1)
    p12 = _midpoint(p1, p2)
    p23 = _midpoint(p2, p3)
    p012 = _midpoint(p01, p12)
    p123 = _midpoint(p12, p23)
    p0123 = _midpoint(p012, p123)

    _append_cubic_points(
        points,
        p0,
        p01,
        p012,
        p0123,
        tolerance=tolerance,
        depth=depth + 1,
    )
    _append_cubic_points(
        points,
        p0123,
        p123,
        p23,
        p3,
        tolerance=tolerance,
        depth=depth + 1,
    )


def _midpoint(left: Vec3, right: Vec3) -> Vec3:
    return (left + right) * 0.5


def _cubic_is_flat_enough(
    p0: Vec3,
    p1: Vec3,
    p2: Vec3,
    p3: Vec3,
    *,
    tolerance: float,
) -> bool:
    return (
        _distance_to_chord(p1, p0, p3) <= tolerance
        and _distance_to_chord(p2, p0, p3) <= tolerance
    )


def _distance_to_chord(point: Vec3, start: Vec3, end: Vec3) -> float:
    direction = end - start
    length = direction.length()
    if length == 0.0:
        return (point - start).length()
    return (point - start).cross(direction).length() / length


@dataclass(frozen=True, slots=True, init=False)
class Polyline3D:
    """Open 3D curve path.

    Passing vertices keeps the older straight-segment construction path.
    Passing curves stores the path as `Line3D`, `Arc3D`, `Spline3D`, or other
    objects implementing `Curve3D`.
    """

    curves: tuple[Curve3D, ...]

    def __init__(self, items: Iterable[Curve3D | Point3Like]) -> None:
        items = tuple(items)
        if not items:
            raise ValueError("Polyline3D requires at least one curve or two vertices")

        curve_flags = tuple(_is_curve3d(item) for item in items)
        if all(curve_flags):
            curves = tuple(cast(Curve3D, item) for item in items)
        elif any(curve_flags):
            raise TypeError(
                "Polyline3D requires all items to be curves or all items to be vertices"
            )
        else:
            vertices = tuple(promote3(cast(Point3Like, item)) for item in items)
            if len(vertices) < 2:
                raise ValueError("Polyline3D requires at least two vertices")
            curves = _line_curves_from_vertices(vertices)

        object.__setattr__(self, "curves", curves)

    @classmethod
    def from_curves(
        cls,
        curves: Iterable[Curve3D],
        *,
        tolerance: float | None = None,
    ) -> Polyline3D:
        polyline = cls(tuple(curves))
        if tolerance is None:
            return polyline
        return polyline.discretise(tolerance=tolerance)

    @property
    def vertices(self) -> tuple[Vec3, ...]:
        return _path_points(self.curves)

    def bounds(self) -> tuple[Vec3, Vec3]:
        curve_bounds = tuple(bound for curve in self.curves for bound in curve.bounds())
        return _bounds(curve_bounds)

    def points(self) -> tuple[Vec3, ...]:
        return self.vertices

    def add(self, curve: Curve3D) -> Polyline3D:
        if not _is_curve3d(curve):
            raise TypeError("Polyline3D.add requires a Curve3D")
        return Polyline3D((*self.curves, curve))

    def discretise(self, *, tolerance: float) -> Polyline3D:
        return Polyline3D(_discretised_points(self.curves, tolerance=tolerance))

    def discretize(self, *, tolerance: float) -> Polyline3D:
        return self.discretise(tolerance=tolerance)

    def to_array(self, *, tolerance: float) -> ArrayPolyline3:
        return _polyline3(_discretised_points(self.curves, tolerance=tolerance))


@dataclass(frozen=True, slots=True, init=False)
class ClosedPolyline3D:
    """Planar closed 3D boundary loop."""

    vertices: tuple[Vec3, ...]

    def __init__(self, vertices: Iterable[Point3Like]) -> None:
        vertices = _dedupe_closed(tuple(promote3(point) for point in vertices))
        object.__setattr__(self, "vertices", vertices)
        if _unique_vertex_count(vertices) < 3:
            raise ValueError("ClosedPolyline3D requires at least three unique vertices")

    def bounds(self) -> tuple[Vec3, Vec3]:
        return _bounds(self.vertices)

    def points(self) -> tuple[Vec3, ...]:
        return self.vertices + (self.vertices[0],)

    def to_array(self, *, tolerance: float) -> ArrayPolyline3:
        positive_tolerance(tolerance)
        import numpy as np

        from cady.operations.arrays3d import ArrayPolyline3

        return ArrayPolyline3(
            np.array([vertex.tuple() for vertex in self.points()], dtype=np.float64)
        )

    def to_mesh(self, *, tolerance: float) -> Mesh3D:
        tolerance = positive_tolerance(tolerance)

        import numpy as np

        from cady.geometry.mesh3d import Mesh3D
        from cady.operations.mesh_caps import triangulate_loop
        from cady.operations.planes import fit_plane_svd, max_plane_deviation, project_loop

        vertex_arrays = [np.array(vertex.tuple(), dtype=np.float64) for vertex in self.vertices]
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
        return Mesh3D(self.vertices, faces, loop_edges(len(self.vertices)))


__all__ = [
    "Arc3D",
    "ClosedPolyline3D",
    "Curve3D",
    "Line3D",
    "Point3Like",
    "Polyline3D",
    "Spline3D",
]
