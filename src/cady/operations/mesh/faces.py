"""Polygon face merging, simplification, and triangulation algorithms."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import TypeAlias

import numpy as np

from cady.operations.mesh.cleanup import compact_polygon_mesh
from cady.operations.plane_fitting import (
    fit_plane,
    plane_coordinates,
    plane_max_deviation,
    plane_point,
)
from cady.operations.primitives import cross3, dot3, length3, scale3, sub3
from cady.operations.triangulate import triangulate

Point3: TypeAlias = Sequence[float]
FaceIndex: TypeAlias = tuple[int, ...]
TriangleIndex: TypeAlias = tuple[int, int, int]
EdgeIndex: TypeAlias = tuple[int, int]


def face_edges(faces: tuple[FaceIndex, ...]) -> tuple[EdgeIndex, ...]:
    """Return the unique undirected edges of polygon faces."""
    edges: set[EdgeIndex] = set()
    for face in faces:
        indices = tuple(int(index) for index in face)
        for start, end in zip(indices, indices[1:] + indices[:1], strict=True):
            edges.add(_edge_key(start, end))
    return tuple(sorted(edges))


def reverse_face_winding(faces: tuple[FaceIndex, ...]) -> tuple[FaceIndex, ...]:
    """Reverse polygon winding while preserving each face's first vertex."""
    return tuple((face[0], *reversed(face[1:])) for face in faces)


def triangulated_faces(
    vertices: tuple[Point3, ...],
    faces: tuple[FaceIndex, ...],
    *,
    tolerance: float,
) -> tuple[TriangleIndex, ...]:
    """Triangulate polygon faces without adding vertices."""
    triangles: list[TriangleIndex] = []
    for face in faces:
        if len(face) == 3:
            triangles.append((int(face[0]), int(face[1]), int(face[2])))
        else:
            triangles.extend(_triangulated_polygon_face(vertices, face, tolerance=tolerance))
    return tuple(triangles)


def merge_coplanar_faces_data(
    vertices: tuple[Point3, ...],
    faces: tuple[FaceIndex, ...],
    *,
    tolerance: float,
) -> tuple[tuple[Point3, ...], tuple[FaceIndex, ...], tuple[EdgeIndex, ...]]:
    """Merge connected coplanar faces and compact the resulting polygon mesh."""
    merged_faces: list[FaceIndex] = []
    for group in _coplanar_face_groups(vertices, faces, tolerance=tolerance):
        if len(group.indices) > 1 and group.boundary is not None:
            merged_faces.append(group.boundary)
        else:
            merged_faces.extend(faces[index] for index in group.indices)
    if not merged_faces:
        return vertices, (), ()

    simplified_faces = tuple(
        _simplified_face_boundary(vertices, face, tolerance=tolerance) for face in merged_faces
    )
    return compact_polygon_mesh(vertices, simplified_faces, face_edges(simplified_faces))


def triangulate_mesh_data(
    vertices: tuple[Point3, ...],
    faces: tuple[FaceIndex, ...],
    *,
    tolerance: float,
    algorithm: str,
    target_edge_length: float | None,
    max_edge_length: float | None,
    max_area: float | None,
    min_angle_degrees: float | None,
) -> tuple[tuple[Point3, ...], tuple[TriangleIndex, ...], tuple[EdgeIndex, ...]]:
    """Merge coplanar polygon faces, then triangulate them."""
    merged_vertices, merged_faces, _edges = merge_coplanar_faces_data(
        vertices,
        faces,
        tolerance=tolerance,
    )
    face_groups = tuple(
        _FaceGroup((index,), face) for index, face in enumerate(merged_faces)
    )
    return _triangulated_mesh(
        merged_vertices,
        merged_faces,
        face_groups,
        tolerance=tolerance,
        algorithm=algorithm,
        target_edge_length=target_edge_length,
        max_edge_length=max_edge_length,
        max_area=max_area,
        min_angle_degrees=min_angle_degrees,
    )


def _simplified_face_boundary(
    vertices: tuple[Point3, ...],
    face: FaceIndex,
    *,
    tolerance: float,
) -> FaceIndex:
    simplified: list[int] = list(face)
    while len(simplified) > 3:
        next_face: list[int] = [
            current
            for index, current in enumerate(simplified)
            if not _is_straight_boundary_vertex(
                vertices,
                simplified[index - 1],
                current,
                simplified[(index + 1) % len(simplified)],
                tolerance=tolerance,
            )
        ]
        if len(next_face) < 3 or len(next_face) == len(simplified):
            break
        simplified = next_face
    return tuple(simplified)


def _is_straight_boundary_vertex(
    vertices: tuple[Point3, ...],
    previous: int,
    current: int,
    following: int,
    *,
    tolerance: float,
) -> bool:
    before = sub3(vertices[current], vertices[previous])
    after = sub3(vertices[following], vertices[current])
    before_length = length3(before)
    after_length = length3(after)
    if before_length <= tolerance or after_length <= tolerance:
        return True
    if dot3(before, after) <= 0.0:
        return False
    return length3(cross3(before, after)) <= tolerance * max(before_length, after_length)


def _fan_triangulated_face(face: FaceIndex) -> tuple[TriangleIndex, ...]:
    return tuple(
        (int(face[0]), int(face[index]), int(face[index + 1]))
        for index in range(1, len(face) - 1)
    )


def _triangulated_mesh(
    vertices: tuple[Point3, ...],
    faces: tuple[FaceIndex, ...],
    face_groups: tuple[_FaceGroup, ...],
    *,
    tolerance: float,
    algorithm: str,
    target_edge_length: float | None,
    max_edge_length: float | None,
    max_area: float | None,
    min_angle_degrees: float | None,
) -> tuple[tuple[Point3, ...], tuple[TriangleIndex, ...], tuple[EdgeIndex, ...]]:
    output_vertices = list(vertices)
    output_faces: list[TriangleIndex] = []
    output_edges: set[EdgeIndex] = set()

    for group in face_groups:
        if len(group.indices) > 1 and group.boundary is not None:
            _extend_triangulated_face_group(
                vertices,
                faces,
                group,
                output_vertices,
                output_faces,
                output_edges,
                tolerance=tolerance,
                algorithm=algorithm,
                target_edge_length=target_edge_length,
                max_edge_length=max_edge_length,
                max_area=max_area,
                min_angle_degrees=min_angle_degrees,
            )
            continue

        for face_index in group.indices:
            _extend_triangulated_face(
                vertices,
                faces[face_index],
                output_vertices,
                output_faces,
                output_edges,
                tolerance=tolerance,
                algorithm=algorithm,
                target_edge_length=target_edge_length,
                max_edge_length=max_edge_length,
                max_area=max_area,
                min_angle_degrees=min_angle_degrees,
            )

    return tuple(output_vertices), tuple(output_faces), tuple(sorted(output_edges))


def _extend_triangulated_face(
    vertices: tuple[Point3, ...],
    face: FaceIndex,
    output_vertices: list[Point3],
    output_faces: list[TriangleIndex],
    output_edges: set[EdgeIndex],
    *,
    tolerance: float,
    algorithm: str,
    target_edge_length: float | None,
    max_edge_length: float | None,
    max_area: float | None,
    min_angle_degrees: float | None,
) -> None:
    points = tuple(vertices[index] for index in face)
    plane = fit_plane(points)
    deviation = plane_max_deviation(plane, points)
    if deviation > tolerance:
        raise ValueError(
            f"3D face is non-planar (max deviation {deviation:.3e} > "
            f"tolerance {tolerance:.3e})"
        )
    nodes = np.asarray([plane_coordinates(plane, point) for point in points], dtype=np.float64)
    boundary = np.asarray(
        tuple((index, (index + 1) % len(face)) for index in range(len(face))),
        dtype=np.int64,
    )
    nodes_out, edges_out, local_faces = triangulate(
        nodes,
        boundary,
        algorithm=algorithm,
        tolerance=tolerance,
        **_triangulation_constraints(
            target_edge_length=target_edge_length,
            max_edge_length=max_edge_length,
            max_area=max_area,
            min_angle_degrees=min_angle_degrees,
        ),
    )
    index_map = list(face)
    for index in range(len(face), len(nodes_out)):
        index_map.append(len(output_vertices))
        x, y = nodes_out[index]
        output_vertices.append(plane_point(plane, float(x), float(y)))

    for a, b, c in local_faces:
        output_faces.append((index_map[int(a)], index_map[int(b)], index_map[int(c)]))
    for start, end in edges_out:
        output_edges.add(_edge_key(index_map[int(start)], index_map[int(end)]))


def _extend_triangulated_face_group(
    vertices: tuple[Point3, ...],
    faces: tuple[FaceIndex, ...],
    group: _FaceGroup,
    output_vertices: list[Point3],
    output_faces: list[TriangleIndex],
    output_edges: set[EdgeIndex],
    *,
    tolerance: float,
    algorithm: str,
    target_edge_length: float | None,
    max_edge_length: float | None,
    max_area: float | None,
    min_angle_degrees: float | None,
) -> None:
    boundary = group.boundary
    if boundary is None:
        return
    _extend_triangulated_face(
        vertices,
        boundary,
        output_vertices,
        output_faces,
        output_edges,
        tolerance=tolerance,
        algorithm=algorithm,
        target_edge_length=target_edge_length,
        max_edge_length=max_edge_length,
        max_area=max_area,
        min_angle_degrees=min_angle_degrees,
    )


def _triangulation_constraints(
    *,
    target_edge_length: float | None,
    max_edge_length: float | None,
    max_area: float | None,
    min_angle_degrees: float | None,
) -> dict[str, float]:
    constraints: dict[str, float] = {}
    if target_edge_length is not None:
        constraints["target_edge_length"] = target_edge_length
    if max_edge_length is not None:
        constraints["max_edge_length"] = max_edge_length
    if max_area is not None:
        constraints["max_area"] = max_area
    if min_angle_degrees is not None:
        constraints["min_angle_degrees"] = min_angle_degrees
    return constraints


@dataclass(frozen=True, slots=True)
class _FaceGroup:
    indices: tuple[int, ...]
    boundary: FaceIndex | None


def _coplanar_face_groups(
    vertices: tuple[Point3, ...],
    faces: tuple[FaceIndex, ...],
    *,
    tolerance: float,
) -> tuple[_FaceGroup, ...]:
    face_planes = tuple(_face_plane(vertices, face, tolerance=tolerance) for face in faces)
    neighbours = _face_neighbours(faces)
    groups: list[_FaceGroup] = []
    visited: set[int] = set()

    for face_index in range(len(faces)):
        if face_index in visited:
            continue

        group = _connected_coplanar_group(
            face_index,
            neighbours,
            face_planes,
            vertices,
            faces,
            tolerance=tolerance,
        )
        visited.update(group)
        groups.append(_face_group(faces, group))

    return tuple(groups)


def _face_group(faces: tuple[FaceIndex, ...], group: tuple[int, ...]) -> _FaceGroup:
    if len(group) == 1:
        return _FaceGroup(group, faces[group[0]])
    return _FaceGroup(group, _simple_boundary_loop(faces[index] for index in group))


def _connected_coplanar_group(
    start: int,
    neighbours: tuple[tuple[int, ...], ...],
    face_planes: tuple[_FacePlane | None, ...],
    vertices: tuple[Point3, ...],
    faces: tuple[FaceIndex, ...],
    *,
    tolerance: float,
) -> tuple[int, ...]:
    start_plane = face_planes[start]
    if start_plane is None:
        return (start,)

    group: list[int] = []
    pending: deque[int] = deque((start,))
    seen = {start}
    while pending:
        face_index = pending.popleft()
        group.append(face_index)
        for neighbour in neighbours[face_index]:
            if neighbour in seen:
                continue
            plane = face_planes[neighbour]
            if plane is None:
                continue
            parallel = _parallel_normals(start_plane.normal, plane.normal, tolerance=tolerance)
            same_plane = _same_plane(start_plane, vertices, faces[neighbour], tolerance=tolerance)
            if parallel and same_plane:
                seen.add(neighbour)
                pending.append(neighbour)

    return tuple(sorted(group))


def _simple_boundary_loop(group_faces: Iterable[FaceIndex]) -> FaceIndex | None:
    edge_counts: defaultdict[EdgeIndex, int] = defaultdict(int)
    directed_edges: list[EdgeIndex] = []
    for face in group_faces:
        for start, end in _directed_face_edges(face):
            edge_counts[_edge_key(start, end)] += 1
            directed_edges.append((start, end))

    boundary_edges = [
        (start, end) for start, end in directed_edges if edge_counts[_edge_key(start, end)] == 1
    ]
    if len(boundary_edges) < 3:
        return None

    next_by_start: dict[int, int] = {}
    for start, end in boundary_edges:
        if start in next_by_start:
            return _undirected_boundary_loop(boundary_edges)
        next_by_start[start] = end

    start = min(next_by_start)
    loop = [start]
    current = start
    while True:
        if current not in next_by_start:
            return _undirected_boundary_loop(boundary_edges)
        current = next_by_start[current]
        if current == start:
            break
        if current in loop:
            return _undirected_boundary_loop(boundary_edges)
        loop.append(current)

    if len(loop) != len(boundary_edges):
        return _undirected_boundary_loop(boundary_edges)
    return tuple(loop)


def _undirected_boundary_loop(boundary_edges: Iterable[EdgeIndex]) -> FaceIndex | None:
    neighbours: defaultdict[int, list[int]] = defaultdict(list)
    edge_count = 0
    for start, end in boundary_edges:
        neighbours[start].append(end)
        neighbours[end].append(start)
        edge_count += 1

    if any(len(values) != 2 for values in neighbours.values()):
        return None

    start = min(neighbours)
    previous = None
    current = start
    loop: list[int] = []
    while True:
        loop.append(current)
        options = neighbours[current]
        next_value = options[0] if options[0] != previous else options[1]
        previous, current = current, next_value
        if current == start:
            break
        if current in loop:
            return None

    if len(loop) != edge_count:
        return None
    return tuple(loop)


def _face_neighbours(faces: tuple[FaceIndex, ...]) -> tuple[tuple[int, ...], ...]:
    faces_by_edge: defaultdict[EdgeIndex, list[int]] = defaultdict(list)
    for face_index, face in enumerate(faces):
        for edge in _directed_face_edges(face):
            faces_by_edge[_edge_key(*edge)].append(face_index)

    neighbours: list[set[int]] = [set() for _ in faces]
    for face_indices in faces_by_edge.values():
        for face_index in face_indices:
            neighbours[face_index].update(index for index in face_indices if index != face_index)
    return tuple(tuple(sorted(values)) for values in neighbours)


@dataclass(frozen=True, slots=True)
class _FacePlane:
    point: Point3
    normal: Point3


def _face_plane(
    vertices: tuple[Point3, ...],
    face: FaceIndex,
    *,
    tolerance: float,
) -> _FacePlane | None:
    points = tuple(vertices[index] for index in face)
    origin = points[0]
    for index in range(1, len(points) - 1):
        normal = cross3(sub3(points[index], origin), sub3(points[index + 1], origin))
        length = length3(normal)
        if length > tolerance:
            return _FacePlane(origin, _canonical_normal(scale3(normal, 1.0 / length), tolerance))
    return None


def _same_plane(
    plane: _FacePlane,
    vertices: tuple[Point3, ...],
    face: FaceIndex,
    *,
    tolerance: float,
) -> bool:
    return all(
        abs(dot3(sub3(vertices[index], plane.point), plane.normal)) <= tolerance
        for index in face
    )


def _parallel_normals(left: Point3, right: Point3, *, tolerance: float) -> bool:
    return 1.0 - abs(dot3(left, right)) <= tolerance


def _directed_face_edges(face: FaceIndex) -> tuple[EdgeIndex, ...]:
    return tuple(zip(face, face[1:] + face[:1], strict=True))


def _edge_key(start: int, end: int) -> EdgeIndex:
    return (min(start, end), max(start, end))


def _canonical_normal(normal: Point3, tolerance: float) -> Point3:
    for component in normal:
        if abs(component) <= tolerance:
            continue
        if component < 0.0:
            return (-normal[0], -normal[1], -normal[2])
        break
    return normal


def _triangulated_polygon_face(
    vertices: tuple[Point3, ...],
    face: FaceIndex,
    *,
    tolerance: float,
) -> tuple[TriangleIndex, ...]:
    points = tuple(vertices[index] for index in face)
    plane = fit_plane(points)
    projected = np.asarray(
        [plane_coordinates(plane, point) for point in points],
        dtype=np.float64,
    )
    boundary = np.asarray(
        tuple((index, (index + 1) % len(face)) for index in range(len(face))),
        dtype=np.int64,
    )
    _nodes, _edges, local_faces = triangulate(projected, boundary, tolerance=tolerance)
    if len(local_faces) == 0:
        return _fan_triangulated_face(face)
    return tuple(
        (int(face[int(a)]), int(face[int(b)]), int(face[int(c)])) for a, b, c in local_faces
    )

