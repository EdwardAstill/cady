from __future__ import annotations

from math import cos, radians

import numpy as np

EDGE_ANGLE_TOLERANCE_DEGREES = 15.0
CURVED_PATCH_ANGLE_TOLERANCE_DEGREES = 35.0
MIN_CURVED_PATCH_ROOTS = 4
MAX_CURVED_PATCH_ROOT_FACES = 4


def orientation_edges(
    vertices: np.ndarray,
    faces: np.ndarray,
    *,
    angle_tolerance_degrees: float = EDGE_ANGLE_TOLERANCE_DEGREES,
    include_boundary_edges: bool = True,
) -> np.ndarray:
    """Return visible mesh edges, suppressing smooth tessellation diagonals."""
    if len(faces) == 0:
        return np.empty((0, 2), dtype=np.uint32)

    normals, valid_normals = _face_normals(vertices, faces)
    edge_faces, edge_indices = _coordinate_edge_ownership(vertices, faces, valid_normals)
    smooth_roots = _smooth_face_roots(
        normals,
        edge_faces,
        angle_tolerance_degrees=angle_tolerance_degrees,
    )

    visible: list[tuple[int, int]] = []
    for edge, owners in edge_faces.items():
        representative = edge_indices[edge]
        owner_roots = {int(smooth_roots[owner]) for owner in owners}
        if len(owner_roots) > 1 or (len(owners) == 1 and include_boundary_edges):
            visible.append(representative)

    return np.array(sorted(visible), dtype=np.uint32).reshape((-1, 2))


def shaded_face_buffers(
    vertices: np.ndarray,
    faces: np.ndarray,
    *,
    angle_tolerance_degrees: float = EDGE_ANGLE_TOLERANCE_DEGREES,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Duplicate hard-edge vertices and build smooth normals per face patch."""
    if len(faces) == 0:
        return (
            np.empty((0, 3), dtype=np.float32),
            np.empty((0, 3), dtype=np.uint32),
            np.empty((0, 3), dtype=np.float32),
        )

    normals, valid_normals = _face_normals(vertices, faces)
    edge_faces, _edge_indices = _coordinate_edge_ownership(vertices, faces, valid_normals)
    smooth_roots = _smooth_face_roots(
        normals,
        edge_faces,
        angle_tolerance_degrees=angle_tolerance_degrees,
    )

    coordinate_tolerance = _coordinate_tolerance(vertices)
    render_indices_by_key: dict[tuple[tuple[int, int, int], int], int] = {}
    render_vertices: list[np.ndarray] = []
    normal_sums: list[np.ndarray] = []
    render_faces: list[tuple[int, int, int]] = []

    for face_index, face in enumerate(faces):
        if not valid_normals[face_index]:
            continue

        root = int(smooth_roots[face_index])
        face_render_indices: list[int] = []
        for vertex_index in face:
            original_index = int(vertex_index)
            key = (_vertex_key(vertices[original_index], coordinate_tolerance), root)
            render_index = render_indices_by_key.get(key)
            if render_index is None:
                render_index = len(render_vertices)
                render_indices_by_key[key] = render_index
                render_vertices.append(vertices[original_index])
                normal_sums.append(np.zeros(3, dtype=np.float32))

            face_normal = normals[face_index]
            if float(np.dot(normal_sums[render_index], face_normal)) < 0.0:
                face_normal = -face_normal
            normal_sums[render_index] = normal_sums[render_index] + face_normal
            face_render_indices.append(render_index)

        render_faces.append(
            (face_render_indices[0], face_render_indices[1], face_render_indices[2])
        )

    if not render_vertices:
        return (
            np.empty((0, 3), dtype=np.float32),
            np.empty((0, 3), dtype=np.uint32),
            np.empty((0, 3), dtype=np.float32),
        )

    render_normals = np.array(normal_sums, dtype=np.float32)
    lengths = np.linalg.norm(render_normals, axis=1)
    valid = lengths > 1e-12
    render_normals[valid] = render_normals[valid] / lengths[valid, None]
    return (
        np.array(render_vertices, dtype=np.float32),
        np.array(render_faces, dtype=np.uint32),
        render_normals,
    )


def _face_normals(vertices: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    triangles = vertices[faces]
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    valid = lengths > 1e-12
    normals[valid] = normals[valid] / lengths[valid, None]
    return normals.astype(np.float32, copy=False), valid


def _coordinate_tolerance(vertices: np.ndarray) -> float:
    if len(vertices) == 0:
        return 1e-12
    span = float(np.max(np.ptp(vertices, axis=0)))
    return max(span * 1e-10, 1e-12)


def _vertex_key(vertex: np.ndarray, coordinate_tolerance: float) -> tuple[int, int, int]:
    scaled = np.rint(vertex / coordinate_tolerance).astype(np.int64)
    return (int(scaled[0]), int(scaled[1]), int(scaled[2]))


def _coordinate_edge_ownership(
    vertices: np.ndarray, faces: np.ndarray, valid_faces: np.ndarray
) -> tuple[
    dict[tuple[tuple[int, int, int], tuple[int, int, int]], list[int]],
    dict[tuple[tuple[int, int, int], tuple[int, int, int]], tuple[int, int]],
]:
    coordinate_tolerance = _coordinate_tolerance(vertices)
    edge_faces: dict[tuple[tuple[int, int, int], tuple[int, int, int]], list[int]] = {}
    edge_indices: dict[tuple[tuple[int, int, int], tuple[int, int, int]], tuple[int, int]] = {}
    for face_index, face in enumerate(faces):
        if not valid_faces[face_index]:
            continue
        face_edges = ((face[0], face[1]), (face[1], face[2]), (face[2], face[0]))
        for start, end in face_edges:
            start_index = int(start)
            end_index = int(end)
            start_key = _vertex_key(vertices[start_index], coordinate_tolerance)
            end_key = _vertex_key(vertices[end_index], coordinate_tolerance)
            if start_key == end_key:
                continue
            edge = (start_key, end_key) if start_key <= end_key else (end_key, start_key)
            edge_faces.setdefault(edge, []).append(face_index)
            edge_indices.setdefault(edge, (start_index, end_index))
    return edge_faces, edge_indices


def _smooth_face_roots(
    normals: np.ndarray,
    edge_faces: dict[tuple[tuple[int, int, int], tuple[int, int, int]], list[int]],
    *,
    angle_tolerance_degrees: float,
    curved_patch_angle_tolerance_degrees: float = CURVED_PATCH_ANGLE_TOLERANCE_DEGREES,
) -> np.ndarray:
    cos_tolerance = cos(radians(angle_tolerance_degrees))
    parents = list(range(len(normals)))

    def find(face_index: int) -> int:
        while parents[face_index] != face_index:
            parents[face_index] = parents[parents[face_index]]
            face_index = parents[face_index]
        return face_index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    for owners in edge_faces.values():
        for index, left in enumerate(owners):
            for right in owners[index + 1 :]:
                if abs(float(np.dot(normals[left], normals[right]))) >= cos_tolerance:
                    union(left, right)

    cos_curved_tolerance = cos(radians(curved_patch_angle_tolerance_degrees))
    if cos_curved_tolerance < cos_tolerance:
        roots = [find(face_index) for face_index in range(len(normals))]
        root_face_counts = np.bincount(np.array(roots, dtype=np.int64), minlength=len(normals))
        curved_adjacency: dict[int, set[int]] = {}
        for owners in edge_faces.values():
            for index, left in enumerate(owners):
                for right in owners[index + 1 :]:
                    left_root = find(left)
                    right_root = find(right)
                    if left_root == right_root:
                        continue
                    if (
                        root_face_counts[left_root] > MAX_CURVED_PATCH_ROOT_FACES
                        or root_face_counts[right_root] > MAX_CURVED_PATCH_ROOT_FACES
                    ):
                        continue
                    dot = abs(float(np.dot(normals[left], normals[right])))
                    if dot >= cos_curved_tolerance:
                        curved_adjacency.setdefault(left_root, set()).add(right_root)
                        curved_adjacency.setdefault(right_root, set()).add(left_root)

        visited: set[int] = set()
        for root in tuple(curved_adjacency):
            if root in visited:
                continue
            component: list[int] = []
            stack = [root]
            visited.add(root)
            while stack:
                current = stack.pop()
                component.append(current)
                for neighbour in curved_adjacency.get(current, set()):
                    if neighbour in visited:
                        continue
                    visited.add(neighbour)
                    stack.append(neighbour)

            if len(component) < MIN_CURVED_PATCH_ROOTS:
                continue
            first = component[0]
            for other in component[1:]:
                union(first, other)

    return np.array([find(face_index) for face_index in range(len(normals))], dtype=np.int64)
