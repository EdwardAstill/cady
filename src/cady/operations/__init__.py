"""Public numeric operations helpers re-exported for convenience."""

from collections.abc import Iterable
from typing import TYPE_CHECKING, TypeAlias

from cady.operations.mesh_clipping import (
    close_boundary,
    close_planar_cap,
    close_to_plane,
    cut_mesh_by_plane,
)
from cady.operations.meshes import (
    sphere_triangles,
)
from cady.operations.transforms import Transform2, Transform3
from cady.operations.triangulate import triangulate

Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]

if TYPE_CHECKING:
    from cady.geometry.arc import Arc2, Arc3
    from cady.geometry.body3 import Body3
    from cady.geometry.conic2 import Circle2
    from cady.geometry.line import Line2, Line3
    from cady.geometry.plane3 import Plane3
    from cady.geometry.polyline import Curve3, Polyline2, Polyline3
    from cady.geometry.region import Region2
    from cady.geometry.spline import Spline3


def line2(start: Point2, end: Point2) -> "Line2":
    from cady.geometry.line import Line2

    return Line2(start, end)


def arc2(
    centre: Point2,
    radius: float,
    start_rad: float,
    end_rad: float,
) -> "Arc2":
    from cady.geometry.arc import Arc2

    return Arc2(centre, radius, start_rad, end_rad)


def line3(start: Point3, end: Point3) -> "Line3":
    from cady.geometry.line import Line3

    return Line3(start, end)


def arc3(
    centre: Point3,
    radius: float,
    start_rad: float,
    end_rad: float,
    *,
    x_axis: Point3 = (1.0, 0.0, 0.0),
    y_axis: Point3 = (0.0, 1.0, 0.0),
) -> "Arc3":
    from cady.geometry.arc import Arc3

    return Arc3(
        centre,
        radius,
        start_rad,
        end_rad,
        x_axis=x_axis,
        y_axis=y_axis,
    )


def spline3(control_points: Iterable[Point3]) -> "Spline3":
    from cady.geometry.spline import Spline3

    return Spline3(control_points)


def polyline3(items: Iterable["Curve3 | Point3"], *, closed: bool = False) -> "Polyline3":
    from cady.geometry.polyline import Polyline3

    return Polyline3(items, closed=closed)


def circle2(centre: Point2, radius: float) -> "Circle2":
    from cady.geometry.conic2 import Circle2

    return Circle2(centre, radius)


def polyline2(
    vertices: tuple[Point2, ...],
    *,
    closed: bool = False,
) -> "Polyline2":
    from cady.geometry.polyline import Polyline2

    return Polyline2(vertices, closed=closed)


def region_rectangle(
    width: float,
    height: float,
    *,
    origin: Point2 = (0.0, 0.0),
) -> "Region2":
    from cady.geometry.region import Region2

    return Region2.rectangle(width, height, origin=origin)


def region_circle(radius: float, *, centre: Point2 = (0.0, 0.0)) -> "Region2":
    from cady.geometry.region import Region2

    return Region2.circle(radius, centre=centre)


def box(
    width: float,
    depth: float,
    height: float,
    *,
    plane: "Plane3 | None" = None,
) -> "Body3":
    from cady.geometry.body3 import Body3

    return Body3.box(width=width, depth=depth, height=height, plane=plane)


def cylinder(
    radius: float,
    height: float,
    *,
    plane: "Plane3 | None" = None,
) -> "Body3":
    from cady.geometry.body3 import Body3

    return Body3.cylinder(radius=radius, height=height, plane=plane)


def sphere(
    radius: float,
    *,
    centre: Point3 = (0.0, 0.0, 0.0),
) -> "Body3":
    from cady.geometry.body3 import Body3

    return Body3.sphere(radius=radius, centre=centre)


__all__ = [
    "Transform2",
    "Transform3",
    "arc2",
    "arc3",
    "box",
    "circle2",
    "close_boundary",
    "close_planar_cap",
    "close_to_plane",
    "cut_mesh_by_plane",
    "cylinder",
    "line2",
    "line3",
    "polyline2",
    "polyline3",
    "region_circle",
    "region_rectangle",
    "sphere",
    "sphere_triangles",
    "spline3",
    "triangulate",
]
