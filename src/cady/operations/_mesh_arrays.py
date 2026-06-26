from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from cady.operations.arrays3d import ArrayMesh3


def coerce_mesh(
    mesh_or_vertices: ArrayMesh3 | object,
    faces: object | None,
    edges: object | None = None,
) -> tuple[ArrayMesh3, bool]:
    if isinstance(mesh_or_vertices, ArrayMesh3):
        return mesh_or_vertices, False
    if faces is None:
        raise TypeError("faces must be provided when passing vertices directly")
    vertices_np = np.asarray(mesh_or_vertices, dtype=np.float64)
    faces_np = np.asarray(faces, dtype=np.int64)
    edges_np = (
        np.asarray(edges, dtype=np.int64)
        if edges is not None
        else np.empty((0, 2), dtype=np.int64)
    )
    return ArrayMesh3(vertices_np, faces_np, edges_np), True


def return_mesh(
    mesh: ArrayMesh3,
    as_tuple: bool,
) -> ArrayMesh3 | tuple[
    NDArray[np.float64],
    NDArray[np.int64],
    NDArray[np.int64],
]:
    if as_tuple:
        return mesh.vertices, mesh.faces, mesh.edges
    return mesh
