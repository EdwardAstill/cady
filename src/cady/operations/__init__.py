"""Public numeric operations helpers re-exported for convenience."""

from collections.abc import Iterable
from typing import TYPE_CHECKING, TypeAlias

from cady.operations.arrays import (
    ArrayBezierSpline2,
    as_edges,
    as_faces,
    as_matrix3,
    as_matrix4,
    as_points2,
    as_points3,
    bounds2,
    bounds3,
    evaluate_bezier_spline2,
    polyline2_area,
    polyline2_centroid,
    polyline2_length,
    polyline3_transformed,
    sample_bezier_spline2,
)
from cady.operations.dispatch import discretise, discretize, mesh, triangulate
from cady.operations.distances import (
    ClosestPoints2,
    ClosestPoints3,
    LinePlaneClosestPoint,
    closest_line_plane,
    closest_points_between_segments2,
    closest_points_between_segments3,
    distance,
    signed_distance_to_plane,
)
from cady.operations.intersections import (
    InfiniteLine3,
    LineIntersection2,
    LineIntersection3,
    LinePlaneIntersection,
    intersect,
    line2_line2_intersection,
    line3_line3_intersection,
    line3_plane_intersection,
    plane_plane_intersection,
)
from cady.operations.meshes import (
    close_boundary,
    close_planar_cap,
    cut_mesh_by_plane,
    sphere_triangles,
)
from cady.operations.sampling import (
    arc_points,
    circle_points,
    midpoint,
    offset_point,
    perpendicular,
    segments_for_circle,
)
from cady.operations.transforms import (
    Pose3,
    Transform2,
    Transform3,
    mirror_point2,
    mirror_point3,
    rotate_point2,
    rotate_point3,
    rotation_matrix2,
    rotation_matrix3,
    scale_point2,
    translate_point2,
    translate_point3,
)
from cady.operations.triangulation import (
    area2,
    dedupe_closed,
    triangulate_float32,
    triangulate_polygon,
)

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


def polyline3(items: Iterable["Curve3 | Point3"]) -> "Polyline3":
    from cady.geometry.polyline import Polyline3

    return Polyline3(items)


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
    "ArrayBezierSpline2",
    "ClosestPoints2",
    "ClosestPoints3",
    "InfiniteLine3",
    "LineIntersection2",
    "LineIntersection3",
    "LinePlaneClosestPoint",
    "LinePlaneIntersection",
    "Pose3",
    "Transform2",
    "Transform3",
    "arc_points",
    "arc2",
    "arc3",
    "area2",
    "as_edges",
    "as_faces",
    "as_matrix3",
    "as_matrix4",
    "as_points2",
    "as_points3",
    "box",
    "bounds2",
    "bounds3",
    "circle2",
    "circle_points",
    "close_boundary",
    "close_planar_cap",
    "closest_line_plane",
    "closest_points_between_segments2",
    "closest_points_between_segments3",
    "cut_mesh_by_plane",
    "cylinder",
    "dedupe_closed",
    "discretise",
    "discretize",
    "distance",
    "evaluate_bezier_spline2",
    "intersect",
    "line2",
    "line2_line2_intersection",
    "line3",
    "line3_line3_intersection",
    "line3_plane_intersection",
    "mesh",
    "midpoint",
    "mirror_point2",
    "mirror_point3",
    "offset_point",
    "perpendicular",
    "plane_plane_intersection",
    "polyline2_area",
    "polyline2_centroid",
    "polyline2_length",
    "polyline3_transformed",
    "polyline2",
    "polyline3",
    "region_circle",
    "region_rectangle",
    "rotate_point2",
    "rotate_point3",
    "rotation_matrix2",
    "rotation_matrix3",
    "sample_bezier_spline2",
    "scale_point2",
    "segments_for_circle",
    "signed_distance_to_plane",
    "sphere",
    "sphere_triangles",
    "spline3",
    "translate_point2",
    "translate_point3",
    "triangulate",
    "triangulate_float32",
    "triangulate_polygon",
]
