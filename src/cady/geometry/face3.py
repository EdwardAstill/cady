"""Planar faces built from profiles or sampled point sets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from cady.geometry.frame3 import Frame3, Point3Like
from cady.geometry.mesh3 import Mesh3
from cady.operations._mesh_builders import face_mesh
from cady.operations.arrays2 import ArrayPolygon2
from cady.vec import Vec3, promote3

if TYPE_CHECKING:
    from cady.view import Camera, DisplayStyle, Light
    from cady.view.open_view import Projection
    from cady.view.style import RenderMode


@dataclass(frozen=True, slots=True)
class Face3:
    """Planar 3D face defined by a 2D profile placed in a frame."""

    profile: object
    frame: Frame3

    @classmethod
    def from_profile(
        cls,
        profile: object,
        *,
        frame: Frame3 | None = None,
        origin: Point3Like | None = None,
        normal: Point3Like | None = None,
        x_axis: Point3Like | None = None,
    ) -> Face3:
        if frame is None:
            if origin is None and normal is None and x_axis is None:
                frame = Frame3.world_xy()
            else:
                frame = Frame3.from_normal(
                    Vec3(0.0, 0.0, 0.0) if origin is None else promote3(origin),
                    Vec3(0.0, 0.0, 1.0) if normal is None else promote3(normal),
                    x_axis=x_axis,
                )
        return cls(profile, frame)

    @classmethod
    def from_points(cls, points: object) -> Face3:
        point_tuple = _points(points)
        frame = _frame_from_points(point_tuple)
        return cls(_ProjectedProfile.from_points(point_tuple, frame), frame)

    @classmethod
    def convex_hull(cls, points: object) -> Face3:
        point_tuple = _points(points)
        frame = _frame_from_points(point_tuple)
        projected = tuple(_project(point, frame) for point in point_tuple)
        hull = _convex_hull(projected)
        return cls(_ProjectedProfile(hull), frame)

    def to_mesh(self, *, tolerance: float) -> Mesh3:
        return face_mesh(self.profile, self.frame, tolerance=tolerance)

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
class _ProjectedProfile:
    outer: tuple[tuple[float, float], ...]

    @classmethod
    def from_points(cls, points: tuple[Vec3, ...], frame: Frame3) -> _ProjectedProfile:
        return cls(tuple(_project(point, frame) for point in points))

    def to_array(self, *, tolerance: float) -> ArrayPolygon2:
        return ArrayPolygon2(np.array(self.outer, dtype=np.float64))


def _points(points: object) -> tuple[Vec3, ...]:
    values = tuple(promote3(point) for point in points)  # type: ignore[union-attr]
    if len(values) < 3:
        raise ValueError("a face requires at least three points")
    return values


def _frame_from_points(points: tuple[Vec3, ...]) -> Frame3:
    origin = points[0]
    for first in points[1:]:
        x_axis = first - origin
        try:
            x_axis = x_axis.normalised()
        except ValueError:
            continue
        for second in points[2:]:
            # The first non-collinear triple establishes the local face plane.
            normal = (first - origin).cross(second - origin)
            try:
                return Frame3(origin, x_axis, normal.normalised())
            except ValueError:
                continue
    raise ValueError("face points must not be collinear")


def _project(point: Vec3, frame: Frame3) -> tuple[float, float]:
    offset = point - frame.origin
    return (offset.dot(frame.x_axis), offset.dot(frame.y_axis))


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
