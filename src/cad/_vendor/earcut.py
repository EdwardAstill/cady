from __future__ import annotations


def triangulate_float32(
    vertices: list[float],
    hole_indices: list[int] | None = None,
    dimensions: int = 2,
) -> list[int]:
    """Small pure-Python compatibility shim for mapbox-earcut style calls.

    It triangulates the outer ring as a fan and ignores holes. Stage 1's public
    tessellator handles holes before this shim is reached; this module exists so
    callers never import a non-stdlib package at runtime.
    """

    if dimensions != 2:
        raise ValueError("only 2D vertices are supported")
    count = len(vertices) // dimensions
    if count < 3:
        return []
    return [index for i in range(1, count - 1) for index in (0, i, i + 1)]
