"""Triangulation for closed 2D and planar 3D curve or edge loops."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray

from cady.operations.mesh_topology import edge_loops
from cady.utils import loop_edges

Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]
FaceIndex: TypeAlias = tuple[int, int, int]
PointArray2 = NDArray[np.float64]
PointArray3 = NDArray[np.float64]
EdgeArray = NDArray[np.int64]
FaceArray = NDArray[np.int64]


@dataclass(frozen=True, slots=True)
class TriangulationGuide:
    """Optional constraints for simple boundary-guided triangulation."""

    target_edge_length: float | None = None
    max_edge_length: float | None = None
    max_area: float | None = None
    min_angle_degrees: float | None = None


def triangulate_curve2(
    curve: object,
    *,
    tolerance: float,
    guide: TriangulationGuide | None = None,
):
    """Fill a closed 2D curve and return a ``Mesh2``."""
    from cady.geometry.mesh import Mesh2

    if not getattr(curve, "closed", False):
        raise ValueError("curve must be closed to triangulate")
    to_array = getattr(curve, "to_array", None)
    if not callable(to_array):
        raise TypeError("curve must provide to_array(tolerance=...)")
    nodes = _coerce_points2(to_array(tolerance=tolerance))
    boundary_edges = np.asarray(loop_edges(len(nodes)), dtype=np.int64)
    nodes_out, boundary_edges = _refine_edges2(
        nodes,
        boundary_edges,
        _validate_guide(guide),
    )
    _nodes_out, _all_edges, faces = triangulate_mesh2(
        nodes_out,
        boundary_edges,
        tolerance=tolerance,
    )
    vertices = tuple((float(x), float(y)) for x, y in nodes_out)
    edge_values = tuple((int(a), int(b)) for a, b in boundary_edges)
    face_values = tuple((int(a), int(b), int(c)) for a, b, c in faces)
    return Mesh2(vertices, face_values, edge_values)


def triangulate_curve3(
    curve: object,
    *,
    tolerance: float,
    guide: TriangulationGuide | None = None,
):
    """Fill a closed planar 3D curve and return a ``Mesh3``."""
    from cady.geometry.mesh import Mesh3

    if not getattr(curve, "closed", False):
        raise ValueError("curve must be closed to triangulate")
    to_array = getattr(curve, "to_array", None)
    if not callable(to_array):
        raise TypeError("curve must provide to_array(tolerance=...)")
    nodes = _coerce_points3(to_array(tolerance=tolerance))
    boundary_edges = np.asarray(loop_edges(len(nodes)), dtype=np.int64)
    nodes_out, boundary_edges = _refine_edges3(
        nodes,
        boundary_edges,
        _validate_guide(guide),
    )
    _nodes_out, _all_edges, faces = triangulate_mesh3(
        nodes_out,
        boundary_edges,
        tolerance=tolerance,
    )
    vertices = tuple((float(x), float(y), float(z)) for x, y, z in nodes_out)
    edge_values = tuple((int(a), int(b)) for a, b in boundary_edges)
    face_values = tuple((int(a), int(b), int(c)) for a, b, c in faces)
    return Mesh3(vertices, face_values, edge_values)


def triangulate_mesh2(
    nodes: object,
    edges: object,
    *,
    tolerance: float = 1e-9,
    guide: TriangulationGuide | None = None,
) -> tuple[PointArray2, EdgeArray, FaceArray]:
    """Triangulate closed 2D edge loops and return nodes, edges, and faces."""
    guide = _validate_guide(guide)
    nodes_out, edges_out = _refine_edges2(
        _coerce_points2(nodes),
        _coerce_edges(edges),
        guide,
    )
    faces: list[FaceIndex] = []
    for loop in edge_loops(edges_out):
        faces.extend(_triangulate_loop2(nodes_out, loop, tolerance))
    faces_array = _face_array(faces)
    return nodes_out, _add_internal_edges(edges_out, faces_array), faces_array


def triangulate_mesh3(
    nodes: object,
    edges: object,
    *,
    tolerance: float = 1e-9,
    guide: TriangulationGuide | None = None,
) -> tuple[PointArray3, EdgeArray, FaceArray]:
    """Project planar 3D edge loops and return nodes, edges, and faces."""
    guide = _validate_guide(guide)
    nodes_out, edges_out = _refine_edges3(
        _coerce_points3(nodes),
        _coerce_edges(edges),
        guide,
    )
    faces: list[FaceIndex] = []
    for loop in edge_loops(edges_out):
        projected = _project_loop3(nodes_out, loop, tolerance)
        local_faces = _triangulate_loop2(projected, tuple(range(len(loop))), tolerance)
        faces.extend((loop[a], loop[b], loop[c]) for a, b, c in local_faces)
    faces_array = _face_array(faces)
    return nodes_out, _add_internal_edges(edges_out, faces_array), faces_array


def triangulate2(
    nodes: object,
    edges: object,
    *,
    tolerance: float = 1e-9,
    guide: TriangulationGuide | None = None,
) -> tuple[PointArray2, FaceArray]:
    """Compatibility wrapper returning ``(nodes, faces)`` for 2D loops."""
    nodes_out, _edges, faces = triangulate_mesh2(
        nodes,
        edges,
        tolerance=tolerance,
        guide=guide,
    )
    return nodes_out, faces


def triangulate3(
    nodes: object,
    edges: object,
    *,
    tolerance: float = 1e-9,
    guide: TriangulationGuide | None = None,
) -> tuple[PointArray3, FaceArray]:
    """Compatibility wrapper returning ``(nodes, faces)`` for planar 3D loops."""
    nodes_out, _edges, faces = triangulate_mesh3(
        nodes,
        edges,
        tolerance=tolerance,
        guide=guide,
    )
    return nodes_out, faces


def _coerce_points2(value: object) -> PointArray2:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError("nodes must have shape (n, 2)")
    if not np.all(np.isfinite(array)):
        raise ValueError("nodes must contain only finite values")
    return np.array(array, dtype=np.float64, copy=True)


def _coerce_points3(value: object) -> PointArray3:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("nodes must have shape (n, 3)")
    if not np.all(np.isfinite(array)):
        raise ValueError("nodes must contain only finite values")
    return np.array(array, dtype=np.float64, copy=True)


def _coerce_edges(value: object) -> EdgeArray:
    array = np.asarray(value, dtype=np.int64)
    if array.size == 0:
        return np.empty((0, 2), dtype=np.int64)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError("edges must have shape (n, 2)")
    return np.array(array, dtype=np.int64, copy=True)


def _validate_guide(guide: TriangulationGuide | None) -> TriangulationGuide | None:
    if guide is None:
        return None
    for name in ("target_edge_length", "max_edge_length"):
        value = getattr(guide, name)
        if value is not None and value <= 0.0:
            raise ValueError(f"{name} must be positive")
    if guide.max_area is not None:
        raise NotImplementedError("TriangulationGuide.max_area is not implemented")
    if guide.min_angle_degrees is not None:
        raise NotImplementedError("TriangulationGuide.min_angle_degrees is not implemented")
    return guide


def _guide_edge_length(guide: TriangulationGuide | None) -> float | None:
    if guide is None:
        return None
    values = [value for value in (guide.max_edge_length, guide.target_edge_length) if value]
    return min(values) if values else None


def _refine_edges2(
    nodes: PointArray2,
    edges: EdgeArray,
    guide: TriangulationGuide | None,
) -> tuple[PointArray2, EdgeArray]:
    return _refine_edges(nodes, edges, _guide_edge_length(guide))


def _refine_edges3(
    nodes: PointArray3,
    edges: EdgeArray,
    guide: TriangulationGuide | None,
) -> tuple[PointArray3, EdgeArray]:
    return _refine_edges(nodes, edges, _guide_edge_length(guide))


def _refine_edges(
    nodes: NDArray[np.float64],
    edges: EdgeArray,
    max_length: float | None,
) -> tuple[NDArray[np.float64], EdgeArray]:
    if max_length is None or len(edges) == 0:
        return nodes, edges

    vertices = [np.array(node, dtype=np.float64, copy=True) for node in nodes]
    refined_edges: list[tuple[int, int]] = []
    for start_raw, end_raw in edges:
        start = int(start_raw)
        end = int(end_raw)
        length = float(np.linalg.norm(nodes[end] - nodes[start]))
        segments = max(1, int(ceil(length / max_length)))
        previous = start
        for segment in range(1, segments):
            ratio = segment / segments
            point = nodes[start] + (nodes[end] - nodes[start]) * ratio
            current = len(vertices)
            vertices.append(np.array(point, dtype=np.float64, copy=True))
            refined_edges.append((previous, current))
            previous = current
        refined_edges.append((previous, end))
    return np.asarray(vertices, dtype=np.float64), np.asarray(refined_edges, dtype=np.int64)


def _face_array(faces: list[FaceIndex]) -> FaceArray:
    if not faces:
        return np.empty((0, 3), dtype=np.int64)
    return np.asarray(faces, dtype=np.int64)


def _add_internal_edges(edges: EdgeArray, faces: FaceArray) -> EdgeArray:
    edge_set = {
        (min(int(start), int(end)), max(int(start), int(end)))
        for start, end in edges
        if int(start) != int(end)
    }
    for a, b, c in faces:
        for start, end in ((int(a), int(b)), (int(b), int(c)), (int(c), int(a))):
            if start != end:
                edge_set.add((min(start, end), max(start, end)))
    if not edge_set:
        return np.empty((0, 2), dtype=np.int64)
    return np.asarray(sorted(edge_set), dtype=np.int64)


def _triangulate_loop2(
    nodes: PointArray2,
    loop: tuple[int, ...],
    tolerance: float,
) -> list[FaceIndex]:
    indices = list(loop)
    if len(indices) < 3:
        return []
    if _signed_area2(nodes, indices) < 0.0:
        indices.reverse()

    faces: list[FaceIndex] = []
    guard = len(indices) * len(indices)
    while len(indices) > 3 and guard > 0:
        guard -= 1
        clipped = False
        for position, current in enumerate(indices):
            previous = indices[position - 1]
            following = indices[(position + 1) % len(indices)]
            if _cross2(nodes[previous], nodes[current], nodes[following]) <= tolerance:
                continue
            if any(
                candidate not in {previous, current, following}
                and _point_in_triangle(
                    nodes[candidate],
                    nodes[previous],
                    nodes[current],
                    nodes[following],
                    tolerance,
                )
                for candidate in indices
            ):
                continue
            faces.append((previous, current, following))
            del indices[position]
            clipped = True
            break
        if clipped:
            continue

        for position, current in enumerate(indices):
            previous = indices[position - 1]
            following = indices[(position + 1) % len(indices)]
            if abs(_cross2(nodes[previous], nodes[current], nodes[following])) <= tolerance:
                del indices[position]
                clipped = True
                break
        if not clipped:
            break

    if len(indices) == 3 and abs(_cross2(nodes[indices[0]], nodes[indices[1]], nodes[indices[2]])):
        faces.append((indices[0], indices[1], indices[2]))
    return faces


def _project_loop3(
    nodes: PointArray3,
    loop: tuple[int, ...],
    tolerance: float,
) -> PointArray2:
    points = nodes[list(loop)]
    origin = points.mean(axis=0)
    centered = points - origin
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    normal = vt[-1]
    deviations = np.abs(centered @ normal)
    if len(deviations) and float(np.max(deviations)) > tolerance:
        raise ValueError(
            "3D edge loop is non-planar "
            f"(max deviation {float(np.max(deviations)):.3e} > tolerance {tolerance:.3e})"
        )
    reference = (
        np.array([1.0, 0.0, 0.0], dtype=np.float64)
        if abs(float(normal[0])) < 0.9
        else np.array([0.0, 1.0, 0.0], dtype=np.float64)
    )
    x_axis = np.cross(normal, reference)
    x_axis = x_axis / np.linalg.norm(x_axis)
    y_axis = np.cross(normal, x_axis)
    return np.column_stack((centered @ x_axis, centered @ y_axis)).astype(np.float64)


def _signed_area2(nodes: PointArray2, indices: list[int]) -> float:
    return 0.5 * sum(
        float(nodes[start, 0] * nodes[end, 1] - nodes[end, 0] * nodes[start, 1])
        for start, end in zip(indices, indices[1:] + indices[:1], strict=True)
    )


def _cross2(a: NDArray[np.float64], b: NDArray[np.float64], c: NDArray[np.float64]) -> float:
    return float((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))


def _point_in_triangle(
    point: NDArray[np.float64],
    a: NDArray[np.float64],
    b: NDArray[np.float64],
    c: NDArray[np.float64],
    tolerance: float,
) -> bool:
    return (
        _cross2(a, b, point) >= -tolerance
        and _cross2(b, c, point) >= -tolerance
        and _cross2(c, a, point) >= -tolerance
    )


__all__ = [
    "TriangulationGuide",
    "triangulate2",
    "triangulate3",
    "triangulate_curve2",
    "triangulate_curve3",
    "triangulate_mesh2",
    "triangulate_mesh3",
]
