"""Filled 2D regions and bounded 3D surface regions."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias, TypeGuard, cast

import numpy as np
from numpy.typing import NDArray

from cady.geometry.conic2 import Circle2
from cady.geometry.mesh import Mesh3
from cady.geometry.plane3 import Plane3
from cady.geometry.polyline import Curve2, Polyline2
from cady.geometry.surface import Surface3
from cady.operations.coordinates import cross3, normalised3, sub3
from cady.operations.meshing import surface_region_mesh

Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]
PointArray2: TypeAlias = NDArray[np.float64]

if TYPE_CHECKING:
    from cady.view import Camera, DisplayStyle, Light
    from cady.view.open_view import Projection
    from cady.view.style import RenderMode


@dataclass(frozen=True, slots=True)
class Region2:
    """Planar filled region with one outer loop and optional holes."""

    outer: Curve2
    holes: tuple[Curve2, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "holes", tuple(self.holes))

    @classmethod
    def rectangle(
        cls,
        width: float,
        height: float,
        *,
        origin: Point2 = (0.0, 0.0),
    ) -> Region2:
        return cls(_rectangle_boundary(width, height, origin=origin))

    @classmethod
    def circle(cls, radius: float, *, centre: Point2 = (0.0, 0.0)) -> Region2:
        return cls(Circle2(centre, radius))

    def bounds(self) -> tuple[Point2, Point2]:
        return self.outer.bounds()

    @property
    def boundary(self) -> tuple[Point2, Point2]:
        return self.bounds()

    def points(self) -> tuple[Point2, ...]:
        return self.outer.points()

    def to_array(self, *, tolerance: float) -> PointArray2:
        return self.loops(tolerance=tolerance)[0]

    def loops(self, *, tolerance: float) -> tuple[PointArray2, ...]:
        curves = (self.outer, *self.holes)
        outer = self.outer.to_array(tolerance=tolerance)
        hole_arrays = tuple(hole.to_array(tolerance=tolerance) for hole in self.holes)
        loops = (outer, *hole_arrays)
        for index, (curve, loop) in enumerate(zip(curves, loops, strict=True)):
            if not getattr(curve, "closed", False):
                label = "outer" if index == 0 else f"holes[{index - 1}]"
                raise ValueError(f"region {label} boundary must be closed")
            if len(loop) < 3:
                label = "outer" if index == 0 else f"holes[{index - 1}]"
                raise ValueError(f"region {label} boundary must contain at least three points")
        return loops


@dataclass(frozen=True, slots=True)
class Region3:
    """Bounded region on a parametric surface.

    ``region`` is the 2D parameter domain: its closed loops are interpreted in
    surface ``(u, v)`` coordinates.
    """

    region: object
    surface: Surface3

    @classmethod
    def from_region(
        cls,
        region: object,
        *,
        surface: Surface3 | None = None,
        plane: Plane3 | None = None,
        origin: Point3 | None = None,
        normal: Point3 | None = None,
        x_axis: Point3 | None = None,
    ) -> Region3:
        if surface is None:
            if origin is None and normal is None and x_axis is None:
                surface = Surface3.plane(plane=plane or Plane3.world_xy())
            else:
                surface = Surface3.plane(
                    plane=plane,
                    origin=(0.0, 0.0, 0.0) if origin is None else origin,
                    normal=(0.0, 0.0, 1.0) if normal is None else normal,
                    x_axis=x_axis,
                )
        elif plane is not None or origin is not None or normal is not None or x_axis is not None:
            raise ValueError("surface cannot be combined with plane, origin, normal, or x_axis")
        return cls(region, surface)

    @property
    def plane(self) -> Plane3:
        if self.surface.base_plane is None:
            raise ValueError("non-planar regions do not have a single placement plane")
        return self.surface.base_plane

    def bounds(self) -> tuple[Point3, Point3]:
        parameter_min, parameter_max = _region_parameter_bounds(self.region)
        u_min, v_min = parameter_min
        u_max, v_max = parameter_max
        points = (
            self.surface.point(u_min, v_min),
            self.surface.point(u_max, v_min),
            self.surface.point(u_max, v_max),
            self.surface.point(u_min, v_max),
        )
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

    @classmethod
    def from_points(cls, points: object) -> Region3:
        point_tuple = _points(points)
        plane = _plane_from_points(point_tuple)
        return cls(_ProjectedRegion.from_points(point_tuple, plane), Surface3.plane(plane=plane))

    @classmethod
    def convex_hull(cls, points: object) -> Region3:
        point_tuple = _points(points)
        plane = _plane_from_points(point_tuple)
        projected = tuple(plane.coordinates(point) for point in point_tuple)
        hull = _convex_hull(projected)
        return cls(_ProjectedRegion(hull), Surface3.plane(plane=plane))

    def to_mesh(self, *, tolerance: float) -> Mesh3:
        return surface_region_mesh(self.region, self.surface, tolerance=tolerance)

    def view(
        self,
        *,
        name: str | None = None,
        title: str | None = None,
        camera: Camera | None = None,
        style: DisplayStyle | None = None,
        light: Light | None = None,
        color: tuple[float, float, float] | None = None,
        render_mode: RenderMode | None = None,
        projection: Projection = "orthographic",
        center: bool = True,
        tolerance: float = 1e-3,
    ) -> None:
        from cady.view.open_view import open_target_view

        open_target_view(
            self,
            name=name,
            title=title,
            camera=camera,
            style=style,
            light=light,
            color=color,
            render_mode=render_mode,
            projection=projection,
            center=center,
            tolerance=tolerance,
        )


@dataclass(frozen=True, slots=True)
class _ProjectedRegion:
    outer: tuple[tuple[float, float], ...]

    @classmethod
    def from_points(cls, points: tuple[Point3, ...], plane: Plane3) -> _ProjectedRegion:
        return cls(tuple(plane.coordinates(point) for point in points))

    @property
    def closed(self) -> bool:
        return True

    def bounds(self) -> tuple[Point2, Point2]:
        return (
            (
                min(point[0] for point in self.outer),
                min(point[1] for point in self.outer),
            ),
            (
                max(point[0] for point in self.outer),
                max(point[1] for point in self.outer),
            ),
        )

    @property
    def boundary(self) -> tuple[Point2, Point2]:
        return self.bounds()

    def to_array(self, *, tolerance: float) -> PointArray2:
        return np.array(self.outer, dtype=np.float64, copy=True)


def _region_parameter_bounds(region: object) -> tuple[Point2, Point2]:
    boundary = getattr(region, "boundary", None)
    if _is_bounds2(boundary):
        return boundary
    bounds = getattr(region, "bounds", None)
    if callable(bounds):
        value = bounds()
        if _is_bounds2(value):
            return value
    raise ValueError("region must expose boundary or bounds as 2D min/max points")


def _is_bounds2(value: object) -> TypeGuard[tuple[Point2, Point2]]:
    if not isinstance(value, tuple):
        return False
    values = cast(tuple[object, ...], value)
    if len(values) != 2:
        return False
    left, right = values
    return _is_point2(left) and _is_point2(right)


def _is_point2(value: object) -> TypeGuard[Point2]:
    if not isinstance(value, tuple):
        return False
    values = cast(tuple[object, ...], value)
    return len(values) == 2 and all(isinstance(component, int | float) for component in values)


def _rectangle_boundary(
    width: float,
    height: float,
    *,
    origin: Point2 = (0.0, 0.0),
) -> Polyline2:
    width = float(width)
    height = float(height)
    if width <= 0.0:
        raise ValueError("width must be positive")
    if height <= 0.0:
        raise ValueError("height must be positive")
    return Polyline2(
        (
            origin,
            (origin[0] + width, origin[1]),
            (origin[0] + width, origin[1] + height),
            (origin[0], origin[1] + height),
        ),
        closed=True,
    )


def _points(points: object) -> tuple[Point3, ...]:
    values = tuple(cast(Iterable[Point3], points))
    if len(values) < 3:
        raise ValueError("a region requires at least three points")
    return values


def _plane_from_points(points: tuple[Point3, ...]) -> Plane3:
    origin = points[0]
    for first in points[1:]:
        x_axis = sub3(first, origin)
        try:
            x_axis = normalised3(x_axis)
        except ValueError:
            continue
        for second in points[2:]:
            # The first non-collinear triple establishes the local region plane.
            normal = cross3(sub3(first, origin), sub3(second, origin))
            try:
                return Plane3(origin, x_axis, normalised3(normal))
            except ValueError:
                continue
    raise ValueError("region points must not be collinear")


def _convex_hull(points: tuple[tuple[float, float], ...]) -> tuple[tuple[float, float], ...]:
    ordered = tuple(sorted(set(points)))
    if len(ordered) < 3:
        raise ValueError("convex hull requires at least three unique points")

    def cross(
        origin: tuple[float, float],
        a: tuple[float, float],
        b: tuple[float, float],
    ) -> float:
        return (a[0] - origin[0]) * (b[1] - origin[1]) - (a[1] - origin[1]) * (b[0] - origin[0])

    lower: list[tuple[float, float]] = []
    for point in ordered:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0.0:
            lower.pop()
        lower.append(point)

    upper: list[tuple[float, float]] = []
    for point in reversed(ordered):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0.0:
            upper.pop()
        upper.append(point)

    return tuple(lower[:-1] + upper[:-1])
