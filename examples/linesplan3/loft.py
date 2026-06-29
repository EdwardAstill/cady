
"""Loft longitudinal ship-hull polylines into an open half-hull mesh.

Assumptions:
    x = longitudinal direction
    y = half-breadth / port-starboard direction
    z = vertical direction

This function expects ONE SIDE of the hull, e.g. positive-y half-breadth lines.
Do not include fin/keel/rudder appendage polylines in this first hull loft.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray

from cady.geometry.mesh import Mesh3
from cady.geometry.polyline import Polyline3

Point3: TypeAlias = tuple[float, float, float]
FaceIndex: TypeAlias = tuple[int, int, int]
EdgeIndex: TypeAlias = tuple[int, int]


def loft_polylines(
    polylines: Iterable[Polyline3],
    *,
    tolerance: float = 1e-6,
    station_count: int | None = None,
    section_count: int = 48,
) -> Mesh3:
    """Loft longitudinal hull polylines into a triangulated open mesh.

    Parameters
    ----------
    polylines:
        Longitudinal hull guide curves. Each curve should be mostly monotone in x.

    tolerance:
        Geometric tolerance for duplicate-point removal and degenerate-triangle filtering.

    station_count:
        If None, use the unique x-values already present in the input polylines.
        If an integer, resample the loft at that many evenly spaced x-stations.

    section_count:
        Number of points to resample around each transverse section.
        Higher values give a smoother mesh in the section direction.

    Returns
    -------
    Mesh3
        Open triangulated half-hull mesh.
    """
    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive")
    if section_count < 2:
        raise ValueError("section_count must be at least 2")
    if station_count is not None and station_count < 2:
        raise ValueError("station_count must be None or at least 2")

    curves = tuple(
        _prepare_longitudinal_polyline(polyline, tolerance=tolerance)
        for polyline in polylines
    )

    if len(curves) < 2:
        raise ValueError("loft_polylines requires at least two longitudinal polylines")

    station_xs = _station_values(
        curves,
        station_count=station_count,
        tolerance=tolerance,
    )

    sections: list[NDArray[np.float64]] = []

    for x in station_xs:
        section_points: list[NDArray[np.float64]] = []

        for curve in curves:
            point = _interpolate_curve_at_x(curve, float(x), tolerance=tolerance)
            if point is not None:
                section_points.append(point)

        section_points = _dedupe_points(section_points, tolerance=tolerance)

        if len(section_points) < 2:
            continue

        ordered = _order_section_points(section_points)
        ordered = _dedupe_adjacent_points(ordered, tolerance=tolerance)

        if len(ordered) < 2:
            continue

        section = _resample_section(
            ordered,
            count=section_count,
            tolerance=tolerance,
        )
        sections.append(section)

    if len(sections) < 2:
        raise ValueError("not enough valid stations were found to create a loft")

    grid = np.stack(sections, axis=0)
    vertices_array = grid.reshape((-1, 3))

    faces = _grid_faces(
        station_count=len(sections),
        section_count=section_count,
        vertices=vertices_array,
        area_tolerance=tolerance * tolerance,
    )

    if not faces:
        raise ValueError("loft produced no non-degenerate faces")

    edges = _edges_from_faces(faces)

    vertices: tuple[Point3, ...] = tuple(
        (float(x), float(y), float(z)) for x, y, z in vertices_array
    )

    return Mesh3(vertices, faces, edges)


def _polyline_array(
    polyline: Polyline3,
    *,
    tolerance: float,
) -> NDArray[np.float64]:
    """Return an Nx3 float array from a Polyline3-like object."""
    to_array = getattr(polyline, "to_array", None)
    if callable(to_array):
        array = to_array(tolerance=tolerance)
    else:
        points = getattr(polyline, "points", None)
        if not callable(points):
            raise TypeError(f"{type(polyline).__name__} is not a Polyline3-like object")
        array = np.asarray(points(), dtype=np.float64)

    array = np.asarray(array, dtype=np.float64)

    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("polyline samples must have shape (n, 3)")

    finite_mask = np.all(np.isfinite(array), axis=1)
    array = array[finite_mask]

    if len(array) < 2:
        raise ValueError("each longitudinal polyline must contain at least two finite points")

    return array


def _prepare_longitudinal_polyline(
    polyline: Polyline3,
    *,
    tolerance: float,
) -> NDArray[np.float64]:
    """Sort a polyline by x and collapse duplicate x-values.

    This turns each longitudinal curve into a function:

        x -> (y, z)

    That is the key assumption of this loft.
    """
    array = _polyline_array(polyline, tolerance=tolerance)

    order = np.argsort(array[:, 0], kind="mergesort")
    array = array[order]

    collapsed: list[NDArray[np.float64]] = []
    start = 0

    while start < len(array):
        end = start + 1
        while end < len(array) and abs(array[end, 0] - array[start, 0]) <= tolerance:
            end += 1

        group = array[start:end]
        collapsed.append(group.mean(axis=0))
        start = end

    result = np.vstack(collapsed)

    if len(result) < 2 or result[-1, 0] - result[0, 0] <= tolerance:
        raise ValueError(
            "each input polyline must span a non-zero x-range; "
            "station/transverse curves cannot be lofted by this function"
        )

    return result


def _station_values(
    curves: tuple[NDArray[np.float64], ...],
    *,
    station_count: int | None,
    tolerance: float,
) -> NDArray[np.float64]:
    """Choose x-stations for the loft."""
    if station_count is not None:
        min_x = min(float(curve[0, 0]) for curve in curves)
        max_x = max(float(curve[-1, 0]) for curve in curves)
        return np.linspace(min_x, max_x, int(station_count), dtype=np.float64)

    values = np.concatenate([curve[:, 0] for curve in curves])
    values = np.sort(values)

    unique: list[float] = []
    for value in values:
        value = float(value)
        if not unique or abs(value - unique[-1]) > tolerance:
            unique.append(value)

    return np.asarray(unique, dtype=np.float64)


def _interpolate_curve_at_x(
    curve: NDArray[np.float64],
    x: float,
    *,
    tolerance: float,
) -> NDArray[np.float64] | None:
    """Interpolate one longitudinal curve at station x.

    Returns None when the curve does not exist at this x-station.
    This is useful for buttocks that only exist over part of the hull.
    """
    x_min = float(curve[0, 0])
    x_max = float(curve[-1, 0])

    if x < x_min - tolerance or x > x_max + tolerance:
        return None

    x_clamped = min(max(x, x_min), x_max)

    xs = curve[:, 0]
    y = float(np.interp(x_clamped, xs, curve[:, 1]))
    z = float(np.interp(x_clamped, xs, curve[:, 2]))

    return np.asarray((x_clamped, y, z), dtype=np.float64)


def _dedupe_points(
    points: list[NDArray[np.float64]],
    *,
    tolerance: float,
) -> list[NDArray[np.float64]]:
    """Remove near-duplicate 3D points while preserving first occurrence."""
    kept: list[NDArray[np.float64]] = []

    for point in points:
        if any(float(np.linalg.norm(point - existing)) <= tolerance for existing in kept):
            continue
        kept.append(point)

    return kept


def _order_section_points(
    points: list[NDArray[np.float64]],
) -> list[NDArray[np.float64]]:
    """Order section points from keel/bottom toward sheer/deck.

    For your generated linesplan, z increases from keel to deck and y generally
    increases outward, so this simple ordering is appropriate.

    If you later handle flare, tumblehome, bulbs, or full port+starboard
    sections, replace this with a proper section-curve fitting/order routine.
    """
    return sorted(points, key=lambda p: (float(p[2]), abs(float(p[1]))))


def _dedupe_adjacent_points(
    points: list[NDArray[np.float64]],
    *,
    tolerance: float,
) -> list[NDArray[np.float64]]:
    """Remove duplicate neighbours after section ordering."""
    kept: list[NDArray[np.float64]] = []

    for point in points:
        if kept and float(np.linalg.norm(point - kept[-1])) <= tolerance:
            continue
        kept.append(point)

    return kept


def _resample_section(
    points: list[NDArray[np.float64]],
    *,
    count: int,
    tolerance: float,
) -> NDArray[np.float64]:
    """Resample one transverse section by arc length."""
    section = np.asarray(points, dtype=np.float64)

    segment_lengths = np.linalg.norm(np.diff(section, axis=0), axis=1)
    keep_mask = np.concatenate(([True], segment_lengths > tolerance))
    section = section[keep_mask]

    if len(section) < 2:
        raise ValueError("section collapsed to fewer than two distinct points")

    segment_lengths = np.linalg.norm(np.diff(section, axis=0), axis=1)
    arc = np.concatenate(([0.0], np.cumsum(segment_lengths)))
    total = float(arc[-1])

    if total <= tolerance:
        raise ValueError("section length is too small to resample")

    targets = np.linspace(0.0, total, count, dtype=np.float64)
    result = np.empty((count, 3), dtype=np.float64)

    for index, target in enumerate(targets):
        segment = int(np.searchsorted(arc, target, side="right") - 1)
        segment = max(0, min(segment, len(arc) - 2))

        denom = arc[segment + 1] - arc[segment]
        alpha = 0.0 if denom <= tolerance else (target - arc[segment]) / denom

        result[index] = (
            section[segment] * (1.0 - alpha)
            + section[segment + 1] * alpha
        )

    return result


def _grid_faces(
    *,
    station_count: int,
    section_count: int,
    vertices: NDArray[np.float64],
    area_tolerance: float,
) -> tuple[FaceIndex, ...]:
    """Create outward-facing triangles for a positive-y half-hull.

    With x forward and section order from keel to deck, the face winding below
    gives normals that generally point toward +y / outward on the starboard side.
    """
    faces: list[FaceIndex] = []

    for i in range(station_count - 1):
        for j in range(section_count - 1):
            a = i * section_count + j
            b = (i + 1) * section_count + j
            c = (i + 1) * section_count + (j + 1)
            d = i * section_count + (j + 1)

            _append_face_if_valid(faces, vertices, (a, c, b), area_tolerance)
            _append_face_if_valid(faces, vertices, (a, d, c), area_tolerance)

    return tuple(faces)


def _append_face_if_valid(
    faces: list[FaceIndex],
    vertices: NDArray[np.float64],
    face: FaceIndex,
    area_tolerance: float,
) -> None:
    a, b, c = face
    area = _triangle_area(vertices[a], vertices[b], vertices[c])

    if area > area_tolerance:
        faces.append(face)


def _triangle_area(
    a: NDArray[np.float64],
    b: NDArray[np.float64],
    c: NDArray[np.float64],
) -> float:
    return 0.5 * float(np.linalg.norm(np.cross(b - a, c - a)))


def _edges_from_faces(faces: tuple[FaceIndex, ...]) -> tuple[EdgeIndex, ...]:
    edges: set[EdgeIndex] = set()

    for a, b, c in faces:
        for start, end in ((a, b), (b, c), (c, a)):
            if start == end:
                continue
            edges.add((min(start, end), max(start, end)))

    return tuple(sorted(edges))
