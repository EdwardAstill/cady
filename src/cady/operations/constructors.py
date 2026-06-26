from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cady.geometry.body3d import Body3D
    from cady.geometry.curves2d import (
        Arc2D,
        Circle2D,
        ClosedPolyline2D,
        Line2D,
        Point2Like,
        Polyline2D,
    )
    from cady.geometry.frame3d import Frame3D, Point3Like
    from cady.geometry.profile2d import Profile2D


def line2d(start: Point2Like, end: Point2Like) -> Line2D:
    from cady.geometry.curves2d import Line2D

    return Line2D(start, end)


def arc2d(centre: Point2Like, radius: float, start_rad: float, end_rad: float) -> Arc2D:
    from cady.geometry.curves2d import Arc2D

    return Arc2D(centre, radius, start_rad, end_rad)


def circle2d(centre: Point2Like, radius: float) -> Circle2D:
    from cady.geometry.curves2d import Circle2D

    return Circle2D(centre, radius)


def polyline2d(
    vertices: tuple[Point2Like, ...],
    *,
    closed: bool = False,
) -> Polyline2D | ClosedPolyline2D:
    from cady.geometry.curves2d import ClosedPolyline2D, Polyline2D

    if closed:
        return ClosedPolyline2D(vertices)
    return Polyline2D(vertices)


def profile_rectangle(
    width: float,
    height: float,
    *,
    origin: Point2Like = (0.0, 0.0),
) -> Profile2D:
    from cady.geometry.profile2d import Profile2D

    return Profile2D.rectangle(width, height, origin=origin)


def profile_circle(radius: float, *, centre: Point2Like = (0.0, 0.0)) -> Profile2D:
    from cady.geometry.profile2d import Profile2D

    return Profile2D.circle(radius, centre=centre)


def box(
    width: float,
    depth: float,
    height: float,
    *,
    frame: Frame3D | None = None,
) -> Body3D:
    from cady.geometry.body3d import Body3D

    return Body3D.box(width=width, depth=depth, height=height, frame=frame)


def cylinder(
    radius: float,
    height: float,
    *,
    frame: Frame3D | None = None,
) -> Body3D:
    from cady.geometry.body3d import Body3D

    return Body3D.cylinder(radius=radius, height=height, frame=frame)


def sphere(
    radius: float,
    *,
    centre: Point3Like = (0.0, 0.0, 0.0),
) -> Body3D:
    from cady.geometry.body3d import Body3D

    return Body3D.sphere(radius=radius, centre=centre)
