"""Clean the final hull mesh through the Mesh3 triangulation API."""

from __future__ import annotations

from cady import Mesh3

TOLERANCE = 1e-3
MIN_TRIANGLE_ANGLE_DEGREES = 20.0


def merge_coplanar_faces(mesh: Mesh3, *, tolerance: float = TOLERANCE) -> Mesh3:
    """Return the intermediate mesh with connected coplanar faces combined."""
    return mesh.merge_coplanar_faces(tolerance=tolerance)


def clean_mesh(mesh: Mesh3, *, tolerance: float = TOLERANCE) -> Mesh3:
    """Return the cleaned triangular hull mesh."""
    return mesh.triangulate(
        tolerance=tolerance,
        guide="auto",
        min_angle_degrees=MIN_TRIANGLE_ANGLE_DEGREES,
    )
