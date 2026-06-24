from __future__ import annotations

from cady.geometry2d.curves import Arc2D, Circle2D, ClosedPolyline2D, Line2D, Point2Like, Polyline2D
from cady.geometry2d.profile import Profile2D


def line2d(start: Point2Like, end: Point2Like) -> Line2D:
    return Line2D(start, end)


def arc2d(centre: Point2Like, radius: float, start_rad: float, end_rad: float) -> Arc2D:
    return Arc2D(centre, radius, start_rad, end_rad)


def circle2d(centre: Point2Like, radius: float) -> Circle2D:
    return Circle2D(centre, radius)


def polyline2d(
    vertices: tuple[Point2Like, ...],
    *,
    closed: bool = False,
) -> Polyline2D | ClosedPolyline2D:
    if closed:
        return ClosedPolyline2D(vertices)
    return Polyline2D(vertices)


def profile_rectangle(
    width: float,
    height: float,
    *,
    origin: Point2Like = (0.0, 0.0),
) -> Profile2D:
    return Profile2D.rectangle(width, height, origin=origin)


def profile_circle(radius: float, *, centre: Point2Like = (0.0, 0.0)) -> Profile2D:
    return Profile2D.circle(radius, centre=centre)
