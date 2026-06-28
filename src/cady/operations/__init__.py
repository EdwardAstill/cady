"""Public numeric operations helpers re-exported for convenience."""

from cady.operations.arrays2 import (
    ArrayBezierSpline2,
    ArrayPolygon2,
    ArrayPolyline2,
    evaluate_bezier_spline2,
    sample_bezier_spline2,
)
from cady.operations.arrays3 import ArrayMesh3, ArrayPolyline3
from cady.operations.bounds import bounds2, bounds3
from cady.operations.constructors import (
    arc2,
    arc3,
    box,
    circle2,
    cylinder,
    line2,
    line3,
    polyline2,
    polyline3,
    profile_circle,
    profile_rectangle,
    sphere,
    spline3,
)
from cady.operations.mesh_caps import close_boundary, close_planar_cap
from cady.operations.mesh_clipping import cut_mesh_by_plane
from cady.operations.mesh_primitives import sphere_triangles
from cady.operations.polygons2 import area2, dedupe_closed, triangulate_polygon
from cady.operations.profiles import midpoint, offset_point, perpendicular
from cady.operations.sampling2 import arc_points, circle_points, segments_for_circle
from cady.operations.transforms import (
    Pose3,
    Transform2,
    Transform3,
    mirror_point2,
    mirror_point3,
    rotate_point2,
    rotate_point3,
    scale_point2,
    translate_point2,
    translate_point3,
)
from cady.operations.triangulation import triangulate_float32
from cady.operations.validation import (
    as_edges,
    as_faces,
    as_matrix3,
    as_matrix4,
    as_points2,
    as_points3,
)

__all__ = [
    "ArrayBezierSpline2",
    "ArrayMesh3",
    "ArrayPolygon2",
    "ArrayPolyline2",
    "ArrayPolyline3",
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
    "cut_mesh_by_plane",
    "cylinder",
    "dedupe_closed",
    "evaluate_bezier_spline2",
    "line2",
    "line3",
    "midpoint",
    "mirror_point2",
    "mirror_point3",
    "offset_point",
    "perpendicular",
    "polyline2",
    "polyline3",
    "profile_circle",
    "profile_rectangle",
    "rotate_point2",
    "rotate_point3",
    "sample_bezier_spline2",
    "scale_point2",
    "segments_for_circle",
    "sphere",
    "sphere_triangles",
    "spline3",
    "translate_point2",
    "translate_point3",
    "triangulate_float32",
    "triangulate_polygon",
]
