"""Mesh-to-render-buffer helpers for the VisPy backend."""

from __future__ import annotations

import numpy as np


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
