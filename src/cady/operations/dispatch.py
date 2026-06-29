"""Smart operation dispatch for semantic and numeric geometry values."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, cast

import numpy as np

from cady.operations.meshes import region_loops_from_region
from cady.operations.triangulation import dedupe_closed, triangulate_polygon
from cady.utils import positive_tolerance

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]

if TYPE_CHECKING:
    from cady.geometry.plane3 import Plane3
    from cady.geometry.surface import Surface3


def discretise(target: object, *, tolerance: float) -> object:
    """Discretise a curve-like value into a polyline-like semantic value."""
    tolerance = positive_tolerance(tolerance)
    method = getattr(target, "discretise", None)
    if callable(method):
        return method(tolerance=tolerance)

    points = _points_from_array_result(_call_to_array(target, tolerance=tolerance))
    if points.shape[1] == 2:
        from cady.geometry.polyline import Polyline2

        vertices2 = tuple((float(x), float(y)) for x, y in points)
        return Polyline2(vertices2, closed=bool(getattr(target, "closed", False)))
    if points.shape[1] == 3:
        from cady.geometry.polyline import Polyline3

        vertices3 = tuple((float(x), float(y), float(z)) for x, y, z in points)
        if bool(getattr(target, "closed", False)):
            return Polyline3(vertices3, closed=True)
        return Polyline3(vertices3)
    raise TypeError("discretise expects 2D or 3D point data")


def discretize(target: object, *, tolerance: float) -> object:
    """American spelling alias for :func:`discretise`."""
    return discretise(target, tolerance=tolerance)


def mesh(
    target: object,
    *,
    tolerance: float,
    surface: object | None = None,
    plane: object | None = None,
    closed: bool = False,
) -> object:
    """Create a mesh from a supported target.

    Dispatches to existing ``to_mesh`` methods first. It also supports
    ``Region2``-like objects, closed 2D/3D curves, point clouds, and bounded
    surface regions supplied as ``mesh(region, surface=...)`` or
    ``mesh(region, plane=...)``.
    """
    tolerance = positive_tolerance(tolerance)
    if _is_mesh_value(target):
        return target

    if surface is not None:
        from cady.geometry.region import Region3

        return Region3.from_region(target, surface=cast("Surface3", surface)).to_mesh(
            tolerance=tolerance
        )
    if plane is not None:
        from cady.operations.meshes import region_mesh

        return region_mesh(target, cast("Plane3", plane), tolerance=tolerance)

    method = getattr(target, "to_mesh", None)
    if callable(method):
        return method(tolerance=tolerance)

    if _is_point_cloud(target):
        return _mesh_from_point_cloud(target, tolerance=tolerance)

    if hasattr(target, "loops"):
        return _mesh2_from_region(target, tolerance=tolerance)

    if bool(getattr(target, "closed", closed)) and hasattr(target, "to_array"):
        return _mesh_from_closed_curve(target, tolerance=tolerance)

    raise TypeError(f"unsupported mesh target: {type(target).__name__}")


def triangulate(
    target: object,
    *,
    tolerance: float,
    surface: object | None = None,
    plane: object | None = None,
) -> object:
    """Triangulate supported polygon, wireframe, curve, or region targets."""
    tolerance = positive_tolerance(tolerance)
    method = getattr(target, "triangulate", None)
    if callable(method):
        return method(tolerance=tolerance)

    polygon = _raw_points2(target)
    if polygon is not None:
        return triangulate_polygon(polygon, tolerance=tolerance)

    return mesh(target, tolerance=tolerance, surface=surface, plane=plane)


def _mesh2_from_region(region: object, *, tolerance: float) -> object:
    from cady.geometry.mesh import Mesh2

    loops = region_loops_from_region(region, tolerance=tolerance)
    outer = loops[0][0]
    holes = tuple(loop for loop, is_hole in loops[1:] if is_hole)
    triangles = triangulate_polygon(outer, holes, tolerance=tolerance)
    vertices: list[Point2] = []
    point_to_index: dict[Point2, int] = {}
    edges: list[tuple[int, int]] = []

    for loop, _is_hole in loops:
        start_index = len(vertices)
        for point in dedupe_closed(loop):
            if point not in point_to_index:
                point_to_index[point] = len(vertices)
                vertices.append(point)
        loop_indices = [point_to_index[point] for point in dedupe_closed(loop)]
        edges.extend(
            (a, b) for a, b in zip(loop_indices, loop_indices[1:] + loop_indices[:1], strict=True)
        )
        if len(vertices) == start_index:
            continue

    faces = tuple(
        (point_to_index[a], point_to_index[b], point_to_index[c]) for a, b, c in triangles
    )
    return Mesh2(tuple(vertices), faces, tuple(edges))


def _mesh_from_closed_curve(target: object, *, tolerance: float) -> object:
    points = _points_from_array_result(_call_to_array(target, tolerance=tolerance))
    if points.shape[1] == 2:
        from cady.geometry.polyline import Polyline2

        vertices2 = tuple((float(x), float(y)) for x, y in points)
        return Polyline2(vertices2, closed=True).to_mesh(tolerance=tolerance)
    if points.shape[1] == 3:
        from cady.geometry.polyline import Polyline3

        vertices3 = tuple((float(x), float(y), float(z)) for x, y, z in points)
        return Polyline3(vertices3, closed=True).to_mesh(tolerance=tolerance)
    raise TypeError("closed curve mesh expects 2D or 3D point data")


def _mesh_from_point_cloud(target: object, *, tolerance: float) -> object:
    points = _points_from_array_result(_call_to_array(target, tolerance=tolerance))
    if points.shape[1] == 2:
        from cady.geometry.mesh import Mesh2

        vertices2 = tuple((float(x), float(y)) for x, y in points)
        return Mesh2(vertices2, ())
    if points.shape[1] == 3:
        from cady.geometry.mesh import Mesh3

        vertices3 = tuple((float(x), float(y), float(z)) for x, y, z in points)
        return Mesh3(vertices3, ())
    raise TypeError("point cloud mesh expects 2D or 3D point data")


def _call_to_array(target: object, *, tolerance: float) -> object:
    method = getattr(target, "to_array", None)
    if not callable(method):
        raise TypeError(f"{type(target).__name__} does not provide to_array(tolerance=...)")
    return method(tolerance=tolerance)


def _points_from_array_result(value: object) -> np.ndarray:
    vertices: object = getattr(value, "vertices", value)
    if isinstance(vertices, tuple) and vertices and isinstance(vertices[0], np.ndarray):
        vertices = cast(object, vertices[0])
    array: np.ndarray = np.array(vertices, dtype=np.float64, copy=True)
    if array.ndim != 2 or array.shape[1] not in {2, 3}:
        raise ValueError("array result must contain 2D or 3D points")
    if not np.all(np.isfinite(array)):
        raise ValueError("array result must contain finite points")
    return array


def _raw_points2(value: object) -> tuple[Point2, ...] | None:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return None
    try:
        array = np.array(value, dtype=np.float64, copy=True)
    except (TypeError, ValueError):
        return None
    if array.ndim != 2 or array.shape[1] != 2 or len(array) < 3:
        return None
    if not np.all(np.isfinite(array)):
        raise ValueError("polygon points must be finite")
    return tuple((float(x), float(y)) for x, y in array)


def _is_point_cloud(target: object) -> bool:
    return type(target).__name__ in {"PointCloud2", "PointCloud3"}


def _is_mesh_value(target: object) -> bool:
    if type(target).__name__ not in {"Mesh2", "Mesh3"}:
        return False
    return hasattr(target, "vertices") and hasattr(target, "faces")


__all__ = ["discretise", "discretize", "mesh", "triangulate"]
