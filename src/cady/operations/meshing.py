"""CAD-facing mesh construction helpers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Protocol, TypeAlias, cast

import numpy as np
from numpy.typing import NDArray

from cady.operations.coordinates import add3, scale3
from cady.operations.triangulation import (
    GuideSpec,
    TriangulationGuide,
    triangulate_curve2,
    triangulate_curve3,
    triangulate_mesh3,
)
from cady.utils import finite, loop_edges, positive_tolerance

if TYPE_CHECKING:
    from cady.geometry.mesh import Mesh2, Mesh3
    from cady.geometry.plane3 import Plane3
    from cady.geometry.surface import Surface3

Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]
Point3Tuple: TypeAlias = tuple[float, float, float]
Triangle2: TypeAlias = tuple[Point2, Point2, Point2]
Triangle3: TypeAlias = tuple[Point3Tuple, Point3Tuple, Point3Tuple]
PointArray2 = NDArray[np.float64]


class _WireframeMeshLike(Protocol):
    vertices: object
    edges: object


def closed_polyline_mesh2(
    polyline: object,
    *,
    tolerance: float,
    guide: GuideSpec = None,
) -> Mesh2:
    """Fill a closed 2D polyline."""
    return triangulate_curve2(polyline, tolerance=tolerance, guide=guide)


def closed_polyline_mesh3(
    polyline: object,
    *,
    tolerance: float,
    guide: GuideSpec = None,
) -> Mesh3:
    """Fill a closed planar 3D polyline."""
    return triangulate_curve3(polyline, tolerance=tolerance, guide=guide)


def wireframe_mesh(
    wireframe: object,
    *,
    tolerance: float,
    guide: GuideSpec = None,
) -> Mesh3:
    """Triangulate closed planar wireframe edge loops into a ``Mesh3``."""
    from cady.geometry.mesh import Mesh3

    source = cast(_WireframeMeshLike, wireframe)
    nodes, edges = source.vertices, source.edges
    nodes_out, edges_out, faces = triangulate_mesh3(
        nodes,
        edges,
        tolerance=tolerance,
        guide=guide,
    )
    vertices = tuple((float(x), float(y), float(z)) for x, y, z in nodes_out)
    edge_values = tuple((int(a), int(b)) for a, b in edges_out)
    face_values = tuple((int(a), int(b), int(c)) for a, b, c in faces)
    return Mesh3(vertices, face_values, edge_values)


def region_mesh(
    region: object,
    plane: Plane3,
    *,
    tolerance: float,
    guide: TriangulationGuide | None = None,
) -> Mesh3:
    from cady.geometry.surface import Surface3

    return surface_region_mesh(
        region,
        Surface3.plane(plane=plane),
        tolerance=tolerance,
        guide=guide,
    )


def surface_region_mesh(
    region: object,
    surface: Surface3,
    *,
    tolerance: float,
    guide: TriangulationGuide | None = None,
) -> Mesh3:
    _reject_unapplied_guide(guide)
    loops = region_loops_from_region(region, tolerance=tolerance)
    outer, holes = _outer_and_holes(loops)
    cap_triangles = triangulate_polygon(
        outer,
        holes,
        tolerance=tolerance,
    )
    triangles = tuple(
        (surface.point(*a), surface.point(*b), surface.point(*c)) for a, b, c in cap_triangles
    )
    return mesh_from_triangles(triangles)


def extrusion_mesh(
    region: object,
    plane: Plane3,
    *,
    distance: float,
    tolerance: float,
    guide: TriangulationGuide | None = None,
) -> Mesh3:
    from cady.geometry.plane3 import Plane3

    _reject_unapplied_guide(guide)
    distance = finite(distance, "distance")
    if distance == 0.0:
        raise ValueError("distance must be finite and non-zero")
    loops = region_loops_from_region(region, tolerance=tolerance)
    outer, holes = _outer_and_holes(loops)
    cap_triangles = triangulate_polygon(
        outer,
        holes,
        tolerance=tolerance,
    )
    end_origin = add3(plane.origin, scale3(plane.normal, distance))
    end_plane = Plane3(end_origin, plane.x_axis, plane.normal)
    triangles: list[Triangle3] = []
    for a, b, c in cap_triangles:
        triangles.append((plane.point(*c), plane.point(*b), plane.point(*a)))
        triangles.append((end_plane.point(*a), end_plane.point(*b), end_plane.point(*c)))
    for loop, is_hole in loops:
        points = dedupe_closed(loop)
        for a, b in zip(points, points[1:] + points[:1], strict=True):
            a0 = plane.point(*a)
            b0 = plane.point(*b)
            a1 = end_plane.point(*a)
            b1 = end_plane.point(*b)
            if is_hole:
                triangles.append((a0, b1, b0))
                triangles.append((a0, a1, b1))
            else:
                triangles.append((a0, b0, b1))
                triangles.append((a0, b1, a1))
    return mesh_from_triangles(tuple(triangles))


def region_loops_from_region(
    region: object,
    *,
    tolerance: float,
) -> tuple[tuple[tuple[Point2, ...], bool], ...]:
    tolerance = positive_tolerance(tolerance)
    loops_method = getattr(region, "loops", None)
    if callable(loops_method):
        raw_loops = cast(Iterable[object], loops_method(tolerance=tolerance))
        loops: tuple[object, ...] = tuple(raw_loops)
        if not loops:
            raise ValueError("region must provide at least one closed loop")
        return tuple(
            (_points_from_closed_polyline(loop, label), is_hole)
            for label, loop, is_hole in _labelled_loops(loops)
        )

    to_array = getattr(region, "to_array", None)
    if to_array is None:
        raise TypeError("region must provide to_array(tolerance=...)")
    loop = to_array(tolerance=tolerance)
    return ((_points_from_closed_polyline(loop, "outer"), False),)


def mesh_from_triangles(triangles: tuple[Triangle3, ...]) -> Mesh3:
    from cady.geometry.mesh import Mesh3

    vertices: list[Point3] = []
    faces: list[tuple[int, int, int]] = []
    for triangle in triangles:
        start = len(vertices)
        vertices.extend(triangle)
        faces.append((start, start + 1, start + 2))
    return Mesh3(tuple(vertices), tuple(faces))


def dedupe_closed(points: tuple[Point2, ...]) -> tuple[Point2, ...]:
    if len(points) > 1 and points[0] == points[-1]:
        return points[:-1]
    return points


def triangulate_polygon(
    outer: tuple[Point2, ...],
    holes: tuple[tuple[Point2, ...], ...] = (),
    *,
    tolerance: float,
) -> list[Triangle2]:
    outer = dedupe_closed(outer)
    holes = tuple(dedupe_closed(hole) for hole in holes)
    if not holes:
        return _triangulate_simple_polygon(outer, tolerance=tolerance)
    return _triangulate_polygon_with_holes(outer, holes, tolerance=tolerance)


def _reject_unapplied_guide(guide: TriangulationGuide | None) -> None:
    if guide is None:
        return
    if (
        guide.target_edge_length is not None
        or guide.max_edge_length is not None
        or guide.max_area is not None
        or guide.min_angle_degrees is not None
    ):
        raise NotImplementedError("TriangulationGuide is not applied to region meshing yet")


def _points2_array(value: object, *, name: str) -> PointArray2:
    try:
        array = np.array(value, dtype=np.float64, copy=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if array.ndim != 2:
        raise ValueError(f"{name} must have rank 2")
    if array.shape[1] != 2:
        raise ValueError(f"{name} must have shape (n, 2)")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    return array


def _points2(points: object) -> tuple[Point2, ...]:
    array = _points2_array(points, name="vertices")
    return tuple((float(point[0]), float(point[1])) for point in array)


def _labelled_loops(
    loops: tuple[object, ...],
) -> tuple[tuple[str, object, bool], ...]:
    labelled = [("outer", loops[0], False)]
    labelled.extend((f"holes[{index}]", loop, True) for index, loop in enumerate(loops[1:]))
    return tuple(labelled)


def _points_from_closed_polyline(loop: object, label: str) -> tuple[Point2, ...]:
    vertices = getattr(loop, "vertices", loop)
    closed = getattr(loop, "closed", True)
    if not closed:
        raise ValueError(f"region {label} boundary must be closed")
    points = dedupe_closed(_points2(vertices))
    if len(points) < 3:
        raise ValueError(f"region {label} boundary must contain at least three points")
    return points


def _outer_and_holes(
    loops: tuple[tuple[tuple[Point2, ...], bool], ...],
) -> tuple[tuple[Point2, ...], tuple[tuple[Point2, ...], ...]]:
    outer = loops[0][0]
    holes = tuple(loop for loop, is_hole in loops[1:] if is_hole)
    return outer, holes


def _area2(points: tuple[Point2, ...]) -> float:
    return (
        sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1], strict=True))
        / 2
    )


def _cross2(a: Point2, b: Point2, c: Point2) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _geometry_tolerance(points: tuple[Point2, ...], tolerance: float) -> float:
    span = max(
        max(point[0] for point in points) - min(point[0] for point in points),
        max(point[1] for point in points) - min(point[1] for point in points),
    )
    return max(span * 1e-12, tolerance * 1e-6, 1e-12)


def _same_point(a: Point2, b: Point2, tolerance: float) -> bool:
    return abs(a[0] - b[0]) <= tolerance and abs(a[1] - b[1]) <= tolerance


def _point_in_poly(point: Point2, poly: tuple[Point2, ...]) -> bool:
    inside = False
    j = len(poly) - 1
    for i, pi_ in enumerate(poly):
        pj = poly[j]
        if ((pi_[1] > point[1]) != (pj[1] > point[1])) and (
            point[0] < (pj[0] - pi_[0]) * (point[1] - pi_[1]) / (pj[1] - pi_[1]) + pi_[0]
        ):
            inside = not inside
        j = i
    return inside


def _point_on_segment(point: Point2, a: Point2, b: Point2, tolerance: float) -> bool:
    if abs(_cross2(a, b, point)) > tolerance:
        return False
    return (
        min(a[0], b[0]) - tolerance <= point[0] <= max(a[0], b[0]) + tolerance
        and min(a[1], b[1]) - tolerance <= point[1] <= max(a[1], b[1]) + tolerance
    )


def _segments_intersect(a: Point2, b: Point2, c: Point2, d: Point2, tolerance: float) -> bool:
    if (
        max(a[0], b[0]) + tolerance < min(c[0], d[0])
        or max(c[0], d[0]) + tolerance < min(a[0], b[0])
        or max(a[1], b[1]) + tolerance < min(c[1], d[1])
        or max(c[1], d[1]) + tolerance < min(a[1], b[1])
    ):
        return False

    ab_c = _cross2(a, b, c)
    ab_d = _cross2(a, b, d)
    cd_a = _cross2(c, d, a)
    cd_b = _cross2(c, d, b)
    if ((ab_c > tolerance and ab_d < -tolerance) or (ab_c < -tolerance and ab_d > tolerance)) and (
        (cd_a > tolerance and cd_b < -tolerance) or (cd_a < -tolerance and cd_b > tolerance)
    ):
        return True
    return (
        abs(ab_c) <= tolerance
        and _point_on_segment(c, a, b, tolerance)
        or abs(ab_d) <= tolerance
        and _point_on_segment(d, a, b, tolerance)
        or abs(cd_a) <= tolerance
        and _point_on_segment(a, c, d, tolerance)
        or abs(cd_b) <= tolerance
        and _point_on_segment(b, c, d, tolerance)
    )


def _clean_ring(points: tuple[Point2, ...]) -> tuple[Point2, ...]:
    clean: list[Point2] = []
    for point in dedupe_closed(points):
        if clean and point == clean[-1]:
            continue
        clean.append(point)
    if len(clean) > 1 and clean[0] == clean[-1]:
        clean.pop()
    return tuple(clean)


def _triangulate_simple_polygon(points: tuple[Point2, ...], *, tolerance: float) -> list[Triangle2]:
    points = _clean_ring(points)
    if len(points) < 3:
        return []
    if _area2(points) < 0:
        points = tuple(reversed(points))

    vertices = np.asarray(points, dtype=np.float64)
    edges = np.asarray(loop_edges(len(points)), dtype=np.int64)
    from cady.operations.triangulation import triangulate2

    _vertices, faces = triangulate2(vertices, edges, tolerance=tolerance)
    return [(points[int(a)], points[int(b)], points[int(c)]) for a, b, c in faces]


def _bridge_is_visible(
    start: Point2,
    end: Point2,
    polygon: tuple[Point2, ...],
    outer: tuple[Point2, ...],
    holes: tuple[tuple[Point2, ...], ...],
    current_hole: int,
    tolerance: float,
) -> bool:
    if _same_point(start, end, tolerance):
        return False

    for fraction in (0.25, 0.5, 0.75):
        sample = (
            start[0] + (end[0] - start[0]) * fraction,
            start[1] + (end[1] - start[1]) * fraction,
        )
        if not _point_in_poly(sample, outer):
            return False
        if any(_point_in_poly(sample, hole) for hole in holes):
            return False

    for a, b in zip(polygon, polygon[1:] + polygon[:1], strict=True):
        if _same_point(a, end, tolerance) or _same_point(b, end, tolerance):
            continue
        if _segments_intersect(start, end, a, b, tolerance):
            return False

    for hole_index, hole in enumerate(holes):
        for a, b in zip(hole, hole[1:] + hole[:1], strict=True):
            if hole_index == current_hole and (
                _same_point(a, start, tolerance) or _same_point(b, start, tolerance)
            ):
                continue
            if _segments_intersect(start, end, a, b, tolerance):
                return False
    return True


def _bridge_hole(
    polygon: tuple[Point2, ...],
    outer: tuple[Point2, ...],
    holes: tuple[tuple[Point2, ...], ...],
    hole_index: int,
    *,
    tolerance: float,
) -> tuple[Point2, ...]:
    hole = holes[hole_index]
    eps = _geometry_tolerance(outer + tuple(point for hole in holes for point in hole), tolerance)
    start_index = max(range(len(hole)), key=lambda index: (hole[index][0], -abs(hole[index][1])))
    start = hole[start_index]
    candidate_indices = list(range(len(polygon)))
    candidate_indices.sort(
        key=lambda index: (
            polygon[index][0] < start[0] - eps,
            (polygon[index][0] - start[0]) ** 2 + (polygon[index][1] - start[1]) ** 2,
        )
    )

    for end_index in candidate_indices:
        end = polygon[end_index]
        if not _bridge_is_visible(start, end, polygon, outer, holes, hole_index, eps):
            continue
        hole_path = hole[start_index:] + hole[:start_index] + (start,)
        return polygon[: end_index + 1] + hole_path + (end,) + polygon[end_index + 1 :]

    raise ValueError("could not connect polygon hole to outer boundary")


def _triangulate_polygon_with_holes(
    outer: tuple[Point2, ...],
    holes: tuple[tuple[Point2, ...], ...],
    *,
    tolerance: float,
) -> list[Triangle2]:
    if _area2(outer) < 0:
        outer = tuple(reversed(outer))
    oriented_holes = tuple(tuple(reversed(hole)) if _area2(hole) > 0 else hole for hole in holes)
    polygon = outer
    for hole_index in sorted(
        range(len(oriented_holes)),
        key=lambda index: max(point[0] for point in oriented_holes[index]),
        reverse=True,
    ):
        polygon = _bridge_hole(
            polygon,
            outer,
            oriented_holes,
            hole_index,
            tolerance=tolerance,
        )
    return _triangulate_simple_polygon(polygon, tolerance=tolerance)


__all__ = [
    "closed_polyline_mesh2",
    "closed_polyline_mesh3",
    "dedupe_closed",
    "extrusion_mesh",
    "mesh_from_triangles",
    "region_loops_from_region",
    "region_mesh",
    "surface_region_mesh",
    "triangulate_polygon",
    "wireframe_mesh",
]
