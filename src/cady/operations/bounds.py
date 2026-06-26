from __future__ import annotations

import numpy as np

from cady.operations.types import PointArray2, PointArray3
from cady.operations.validation import as_points2, as_points3


def bounds2(points: object, *, name: str = "points") -> tuple[PointArray2, PointArray2]:
    array = as_points2(points, name=name)
    if len(array) == 0:
        raise ValueError(f"{name} must contain at least one point")
    return np.min(array, axis=0), np.max(array, axis=0)


def bounds3(points: object, *, name: str = "points") -> tuple[PointArray3, PointArray3]:
    array = as_points3(points, name=name)
    if len(array) == 0:
        raise ValueError(f"{name} must contain at least one point")
    return np.min(array, axis=0), np.max(array, axis=0)
