"""Small fallback triangulation helpers for flat vertex buffers."""

from __future__ import annotations


def triangulate_float32(
    vertices: list[float],
    hole_indices: list[int] | None = None,
    dimensions: int = 2,
) -> list[int]:
    """Triangulate a flat 2D vertex buffer as triangle indices.

    This is a small pure-Python helper for the simple outer-ring cases cady
    currently needs. Holes are handled by higher-level tessellation before this
    function is called.
    """
    if dimensions != 2:
        raise ValueError("only 2D vertices are supported")
    if hole_indices:
        raise ValueError("hole indices are handled by cady.operations.tessellate")
    count = len(vertices) // dimensions
    if count < 3:
        return []
    return [index for i in range(1, count - 1) for index in (0, i, i + 1)]
