"""Simple per-triangle mesh statistics."""

from __future__ import annotations

from collections.abc import Sequence
from math import fsum
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray

FloatArray: TypeAlias = NDArray[np.float64]
Point2: TypeAlias = Sequence[float]
Point3: TypeAlias = Sequence[float]
TriangleIndex: TypeAlias = tuple[int, int, int]


def mesh2_area(
    vertices: tuple[Point2, ...],
    faces: tuple[TriangleIndex, ...],
) -> float:
    """Return the total unsigned area of an indexed 2D triangle mesh."""
    return float(
        fsum(
            abs(_triangle_area2(vertices[a], vertices[b], vertices[c]))
            for a, b, c in faces
        )
    )


def mesh3_area(
    vertices: tuple[Point3, ...],
    faces: tuple[TriangleIndex, ...],
) -> float:
    """Return the total surface area of an indexed 3D triangle mesh."""
    return float(
        fsum(_triangle_area3(vertices[a], vertices[b], vertices[c]) for a, b, c in faces)
    )


def mesh3_volume(
    vertices: tuple[Point3, ...],
    faces: tuple[TriangleIndex, ...],
) -> float:
    """Return absolute enclosed volume using signed tetrahedron integration."""
    if not faces or not vertices:
        return 0.0

    signed_sum = fsum(
        (
            vertices[a][0]
            * (vertices[b][1] * vertices[c][2] - vertices[b][2] * vertices[c][1])
            - vertices[a][1]
            * (vertices[b][0] * vertices[c][2] - vertices[b][2] * vertices[c][0])
            + vertices[a][2]
            * (vertices[b][0] * vertices[c][1] - vertices[b][1] * vertices[c][0])
        )
        / 6.0
        for a, b, c in faces
    )
    return abs(signed_sum)


def face_areas(faces: object) -> FloatArray:
    """Return one area per coordinate triangle.

    ``faces`` must be an array-like value with shape ``(n, 3, 2)`` or
    ``(n, 3, 3)``.
    """
    triangles = _triangle_points(faces)
    if len(triangles) == 0:
        return np.empty(0, dtype=np.float64)

    first = triangles[:, 0]
    second = triangles[:, 1]
    third = triangles[:, 2]
    ab = second - first
    ac = third - first
    if triangles.shape[2] == 2:
        cross = ab[:, 0] * ac[:, 1] - ab[:, 1] * ac[:, 0]
        return np.abs(cross) * 0.5
    return np.linalg.norm(np.cross(ab, ac), axis=1) * 0.5


def radius_ratios(faces: object) -> FloatArray:
    """Return triangle radius ratios, ``R / 2r``.

    ``faces`` may be coordinate triangles with shape ``(n, 3, 2)`` or
    ``(n, 3, 3)``. A ``(n, 3)`` array is treated as triangle side lengths.
    """
    values = np.asarray(faces, dtype=np.float64)
    if values.size == 0:
        return np.empty(0, dtype=np.float64)
    if values.ndim == 2 and values.shape[1] == 3:
        return _radius_ratios_from_lengths(values[:, 0], values[:, 1], values[:, 2])

    triangles = _triangle_points(values)
    first = triangles[:, 0]
    second = triangles[:, 1]
    third = triangles[:, 2]
    ab = np.linalg.norm(second - first, axis=1)
    bc = np.linalg.norm(third - second, axis=1)
    ca = np.linalg.norm(first - third, axis=1)
    return _radius_ratios_from_lengths(ab, bc, ca)


def _radius_ratios_from_lengths(ab: FloatArray, bc: FloatArray, ca: FloatArray) -> FloatArray:
    semiperimeter = (ab + bc + ca) * 0.5
    area_squared = semiperimeter * (semiperimeter - ab) * (semiperimeter - bc) * (
        semiperimeter - ca
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        return ab * bc * ca * semiperimeter / (8.0 * area_squared)


def _triangle_points(faces: object) -> FloatArray:
    values = np.asarray(faces, dtype=np.float64)
    if values.size == 0:
        return np.empty((0, 3, 3), dtype=np.float64)
    if values.ndim != 3 or values.shape[1] != 3 or values.shape[2] not in {2, 3}:
        raise ValueError("faces must have shape (n, 3, 2) or (n, 3, 3)")
    return values


def _triangle_area2(a: Point2, b: Point2, c: Point2) -> float:
    return 0.5 * (
        (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
    )


def _triangle_area3(a: Point3, b: Point3, c: Point3) -> float:
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    cross = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    return 0.5 * (
        cross[0] * cross[0] + cross[1] * cross[1] + cross[2] * cross[2]
    ) ** 0.5
