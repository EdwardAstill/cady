"""Pizza triangulation: convert non-triangular mesh faces to triangles.

Quad faces (4 vertices) are split diagonally into 2 triangles.
N-gon faces (5+ vertices) use pizza/pie triangulation: a centroid vertex is
added and connected to every edge of the polygon.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TypeAlias

import numpy as np

from cady import Mesh3

Point3: TypeAlias = tuple[float, float, float]
Face: TypeAlias = tuple[int, ...]


def pizza_triangulate_mesh(mesh: Mesh3) -> Mesh3:
    """Return a new Mesh3 with all faces triangulated using the pizza strategy.

    Quad faces are split along their shorter diagonal.
    N-gon faces get a centroid vertex and fan triangles to each edge.
    Existing triangle faces pass through unchanged.
    Display edges are recomputed from the triangulated faces so every
    triangle edge is visible.
    """
    new_vertices, new_faces = pizza_triangulate(mesh.vertices, mesh.faces)
    new_edges = _face_edges(new_faces)
    return Mesh3(
        tuple(tuple(v) for v in new_vertices),  # type: ignore[arg-type]
        tuple(tuple(f) for f in new_faces),  # type: ignore[arg-type]
        tuple(sorted(new_edges)),
    )


def pizza_triangulate(
    vertices: Sequence[Point3] | np.ndarray,
    faces: Sequence[Sequence[int]] | np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert faces to all-triangle faces.

    Parameters
    ----------
    vertices : (n, 3) array or sequence of points
        Vertex positions.
    faces : (m, k) array or sequence of index sequences
        Face vertex indices. Each face may have any number of vertices >= 3.

    Returns
    -------
    new_vertices : np.ndarray of shape (n + added, 3)
        Original vertices plus centroid vertices inserted for n-gons.
    new_faces : np.ndarray of shape (t, 3)
        All-triangle face index array.
    """
    V = np.asarray(vertices, dtype=np.float64)

    if isinstance(faces, np.ndarray) and faces.ndim == 2:
        iterable = [list(row) for row in faces]
    else:
        iterable = list(faces)

    new_vertices: list[list[float]] = list(V.tolist())
    new_face_list: list[list[int]] = []

    for face in iterable:
        ids = _clean_face(face)
        n = len(ids)

        if n < 3:
            continue

        if n == 3:
            new_face_list.append(ids)

        elif n == 4:
            new_face_list.extend(_split_quad(V, ids))

        else:
            new_face_list.extend(_fan_from_centroid(V, ids, new_vertices))

    if not new_face_list:
        return (
            np.array(new_vertices, dtype=np.float64),
            np.empty((0, 3), dtype=np.int64),
        )

    return (
        np.array(new_vertices, dtype=np.float64),
        np.array(new_face_list, dtype=np.int64),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _clean_face(face: Iterable[int]) -> list[int]:
    """Remove consecutive duplicates and trailing wrap-around duplicate."""
    ids: list[int] = []
    for x in face:
        ix = int(x)
        if ix < 0:
            continue
        if not ids or ids[-1] != ix:
            ids.append(ix)
    if len(ids) > 1 and ids[0] == ids[-1]:
        ids.pop()
    return ids


def _split_quad(V: np.ndarray, ids: list[int]) -> list[list[int]]:
    """Split a quad into two triangles along the shorter diagonal."""
    a, b, c, d = ids
    diag_ac = float(np.linalg.norm(V[c] - V[a]))
    diag_bd = float(np.linalg.norm(V[d] - V[b]))

    if diag_ac <= diag_bd:
        return [[a, b, c], [a, c, d]]
    else:
        return [[a, b, d], [b, c, d]]


def _face_edges(faces: np.ndarray) -> set[tuple[int, int]]:
    """Extract all unique edges from an (n, 3) triangle face array."""
    edges: set[tuple[int, int]] = set()
    for tri in faces:
        a, b, c = int(tri[0]), int(tri[1]), int(tri[2])
        edges.add((a, b) if a < b else (b, a))
        edges.add((b, c) if b < c else (c, b))
        edges.add((c, a) if c < a else (a, c))
    return edges


def _fan_from_centroid(
    V: np.ndarray,
    ids: list[int],
    new_vertices: list[list[float]],
) -> list[list[int]]:
    """Add a centroid vertex and fan triangles to each polygon edge."""
    centroid_idx = len(new_vertices)
    pts = V[np.asarray(ids, dtype=np.int64)]
    centroid: list[float] = np.mean(pts, axis=0).tolist()
    new_vertices.append(centroid)

    n = len(ids)
    tris: list[list[int]] = []
    for i in range(n):
        tris.append([ids[i], ids[(i + 1) % n], centroid_idx])

    return tris
