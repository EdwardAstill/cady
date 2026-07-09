"""Mesh-to-render-buffer helpers for the VisPy backend."""

from __future__ import annotations

from math import cos, radians

import numpy as np

# This threshold affects generated display edges only; it does not mutate or
# simplify the source Mesh3 topology.
EDGE_ANGLE_TOLERANCE_DEGREES = 15.0


def orientation_edges(
    vertices: np.ndarray,
    faces: np.ndarray,
    *,
    angle_tolerance_degrees: float = EDGE_ANGLE_TOLERANCE_DEGREES,
    include_boundary_edges: bool = True,
) -> np.ndarray:
    """Return visible mesh edges, suppressing coplanar tessellation diagonals."""
    if len(faces) == 0:
        return np.empty((0, 2), dtype=np.uint32)

    normals, valid_normals = _face_normals(vertices, faces)
    edge_faces, edge_indices = _coordinate_edge_ownership(vertices, faces, valid_normals)
    cos_tolerance = cos(radians(angle_tolerance_degrees))

    visible: list[tuple[int, int]] = []
    for edge, owners in edge_faces.items():
        representative = edge_indices[edge]
        if len(owners) == 1:
            if include_boundary_edges:
                visible.append(representative)
            continue
        owner_normals = normals[np.array(owners, dtype=np.int64)]
        reference = owner_normals[0]
        if any(
            abs(float(np.dot(reference, normal))) < cos_tolerance
            for normal in owner_normals[1:]
        ):
            visible.append(representative)

    return np.array(sorted(visible), dtype=np.uint32).reshape((-1, 2))


def flat_face_buffers(
    vertices: np.ndarray,
    faces: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Duplicate each triangle's vertices and assign one normal per face."""
    if len(faces) == 0:
        return (
            np.empty((0, 3), dtype=np.float32),
            np.empty((0, 3), dtype=np.uint32),
            np.empty((0, 3), dtype=np.float32),
        )

    normals, valid_normals = _face_normals(vertices, faces)
    render_vertices: list[np.ndarray] = []
    render_normals: list[np.ndarray] = []
    render_faces: list[tuple[int, int, int]] = []

    for face_index, face in enumerate(faces):
        if not valid_normals[face_index]:
            continue

        start = len(render_vertices)
        face_normal = normals[face_index]
        render_vertices.extend(vertices[int(vertex_index)] for vertex_index in face)
        render_normals.extend((face_normal, face_normal, face_normal))
        render_faces.append((start, start + 1, start + 2))

    if not render_vertices:
        return (
            np.empty((0, 3), dtype=np.float32),
            np.empty((0, 3), dtype=np.uint32),
            np.empty((0, 3), dtype=np.float32),
        )

    return (
        np.array(render_vertices, dtype=np.float32),
        np.array(render_faces, dtype=np.uint32),
        np.array(render_normals, dtype=np.float32),
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
    """Group face edges by quantised endpoint coordinates."""
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
