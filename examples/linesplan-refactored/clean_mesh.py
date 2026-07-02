"""Simplify and triangulate the merged-coplanar final hull mesh."""

from __future__ import annotations

from math import isfinite

from cady import Mesh3
from cady.geometry.plane3 import Plane3

Point3 = tuple[float, float, float]
Face = tuple[int, ...]
Edge = tuple[int, int]
TOLERANCE = 1e-3


def merge_coplanar_faces(mesh: Mesh3, *, tolerance: float = TOLERANCE) -> Mesh3:
    """Return the intermediate mesh with connected coplanar faces combined."""
    return mesh.merge_coplanar_faces(tolerance=tolerance)


def triangulate_non_planar_quads(mesh: Mesh3, *, tolerance: float = TOLERANCE) -> Mesh3:
    """Split only non-planar quad faces into triangles."""
    if not isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("tolerance must be positive")

    faces: list[Face] = []
    for face in mesh.faces:
        if len(face) == 4 and not _is_planar_face(mesh, face, tolerance=tolerance):
            a, b, c, d = face
            faces.append((a, b, c))
            faces.append((a, c, d))
        else:
            faces.append(face)

    return Mesh3(mesh.vertices, tuple(faces), _mesh_edges(tuple(faces), mesh.edges))


def clean_mesh(
    mesh: Mesh3,
    *,
    tolerance: float = TOLERANCE,
    min_angle_degrees: float | None = None,
) -> Mesh3:
    """Return a triangular mesh from an already merged-coplanar mesh."""
    if not isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("tolerance must be positive")
    return mesh.triangulate(
        tolerance=tolerance,
        guide="auto",
        min_angle_degrees=min_angle_degrees,
    )


def top_face_mesh(
    mesh: Mesh3,
    *,
    tolerance: float = TOLERANCE,
) -> Mesh3:
    """Return the uppermost polygon face as its own mesh."""
    if not isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("tolerance must be positive")
    if not mesh.faces:
        raise ValueError("mesh must contain at least one face")

    face = max(mesh.faces, key=lambda item: _face_top_key(mesh, item))
    vertices = tuple(mesh.vertices[index] for index in face)
    local_face = tuple(range(len(vertices)))
    return Mesh3(vertices, (local_face,), _loop_edges(len(vertices)))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _loop_edges(count: int) -> tuple[Edge, ...]:
    return tuple((index, (index + 1) % count) for index in range(count))


def _face_edges(face: Face) -> tuple[Edge, ...]:
    return tuple(
        _edge_key(start, end) for start, end in zip(face, face[1:] + face[:1], strict=True)
    )


def _edge_key(start: int, end: int) -> Edge:
    return (min(start, end), max(start, end))


def _mesh_edges(faces: tuple[Face, ...], display_edges: tuple[Edge, ...]) -> tuple[Edge, ...]:
    edges = set(display_edges)
    for face in faces:
        edges.update(_face_edges(face))
    return tuple(sorted(edges))


def _is_planar_face(mesh: Mesh3, face: Face, *, tolerance: float) -> bool:
    points = tuple(mesh.vertices[index] for index in face)
    plane = Plane3.fit(points)
    return plane.max_deviation(points) <= tolerance


def _face_top_key(mesh: Mesh3, face: Face) -> tuple[float, float, float, int]:
    z_values = tuple(mesh.vertices[index][2] for index in face)
    return (
        sum(z_values) / len(z_values),
        min(z_values),
        max(z_values),
        len(face),
    )
