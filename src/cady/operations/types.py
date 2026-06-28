"""Shared NumPy and tuple type aliases for operations modules."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]
PointArray2 = NDArray[np.float64]
PointArray3 = NDArray[np.float64]
FaceArray = NDArray[np.int64]
EdgeArray = NDArray[np.int64]
Matrix3 = NDArray[np.float64]
Matrix4 = NDArray[np.float64]

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]
