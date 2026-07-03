import numpy as np
from numpy.typing import NDArray

def triangulate(
    nodes: object,
    edges: object,
    *,
    algorithm: str = "ear_delaunay_refinement",
    **constraints: object,
) -> tuple[NDArray[np.float64], NDArray[np.int64], NDArray[np.int64]]: ...
