"""Import-light constructor wrappers for authoring-layer factories."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cady.geometry.arc2 import Arc2
    from cady.geometry.body3 import Body3
    from cady.geometry.conic2 import Circle2
    from cady.geometry.curves2 import Point2Like
    from cady.geometry.frame3 import Frame3, Point3Like
    from cady.geometry.line2 import Line2
    from cady.geometry.polyline2 import ClosedPolyline2, Polyline2
    from cady.geometry.polyline3 import (
        Arc3,
        Curve3,
        Line3,
        Polyline3,
        Spline3,
    )
    from cady.geometry.profile2 import Profile2


def line2(start: Point2Like, end: Point2Like) -> Line2:
    from cady.geometry.line2 import Line2

    return Line2(start, end)


def arc2(centre: Point2Like, radius: float, start_rad: float, end_rad: float) -> Arc2:
    from cady.geometry.arc2 import Arc2

    return Arc2(centre, radius, start_rad, end_rad)


def line3(start: Point3Like, end: Point3Like) -> Line3:
    from cady.geometry.polyline3 import Line3

    return Line3(start, end)


def arc3(
    centre: Point3Like,
    radius: float,
    start_rad: float,
    end_rad: float,
    *,
    x_axis: Point3Like = (1.0, 0.0, 0.0),
    y_axis: Point3Like = (0.0, 1.0, 0.0),
) -> Arc3:
    from cady.geometry.polyline3 import Arc3

    return Arc3(
        centre,
        radius,
        start_rad,
        end_rad,
        x_axis=x_axis,
        y_axis=y_axis,
    )


def spline3(control_points: Iterable[Point3Like]) -> Spline3:
    from cady.geometry.polyline3 import Spline3

    return Spline3(control_points)


def polyline3(items: Iterable[Curve3 | Point3Like]) -> Polyline3:
    from cady.geometry.polyline3 import Polyline3

    return Polyline3(items)


def circle2(centre: Point2Like, radius: float) -> Circle2:
    from cady.geometry.conic2 import Circle2

    return Circle2(centre, radius)


def polyline2(
    vertices: tuple[Point2Like, ...],
    *,
    closed: bool = False,
) -> Polyline2 | ClosedPolyline2:
    from cady.geometry.polyline2 import ClosedPolyline2, Polyline2

    if closed:
        return ClosedPolyline2(vertices)
    return Polyline2(vertices)


def profile_rectangle(
    width: float,
    height: float,
    *,
    origin: Point2Like = (0.0, 0.0),
) -> Profile2:
    from cady.geometry.profile2 import Profile2

    return Profile2.rectangle(width, height, origin=origin)


def profile_circle(radius: float, *, centre: Point2Like = (0.0, 0.0)) -> Profile2:
    from cady.geometry.profile2 import Profile2

    return Profile2.circle(radius, centre=centre)


def box(
    width: float,
    depth: float,
    height: float,
    *,
    frame: Frame3 | None = None,
) -> Body3:
    from cady.geometry.body3 import Body3

    return Body3.box(width=width, depth=depth, height=height, frame=frame)


def cylinder(
    radius: float,
    height: float,
    *,
    frame: Frame3 | None = None,
) -> Body3:
    from cady.geometry.body3 import Body3

    return Body3.cylinder(radius=radius, height=height, frame=frame)


def sphere(
    radius: float,
    *,
    centre: Point3Like = (0.0, 0.0, 0.0),
) -> Body3:
    from cady.geometry.body3 import Body3

    return Body3.sphere(radius=radius, centre=centre)
