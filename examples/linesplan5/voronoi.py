import numpy as np
from numpy.typing import NDArray
from pc_from_dxf import LINESPLAN_DXF, points_from_dxf

from cady import DisplayStyle, PointCloud3, Scene, Wireframe3

NORMAL_LENGTH = 1000.0


def pca_normals(points: NDArray[np.float64], k: int = 10) -> NDArray[np.float64]:
    """
    Compute unoriented normals for a point cloud using PCA.

    Parameters:
    points (numpy.ndarray): Input point cloud as an Nx3 array.
    k (int): Number of nearest neighbors to consider for PCA.

    Returns:
    numpy.ndarray: Nx3 array of normals corresponding to each point.
    """
    points = np.asarray(points, dtype=np.float64)

    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError("points must be an Nx3 array")

    n_points = points.shape[0]

    if n_points < 3:
        raise ValueError("At least 3 points are required to estimate normals")

    if k < 3:
        raise ValueError("k should be at least 3")

    if k >= n_points:
        k = n_points - 1

    nearest_neighbors = np.zeros((n_points, k), dtype=int)

    for i in range(n_points):
        distances = np.linalg.norm(points - points[i], axis=1)
        nearest_neighbors[i] = np.argsort(distances)[1:k + 1]

    normals = np.zeros((n_points, 3), dtype=float)

    for i in range(n_points):
        neighbor_points = points[nearest_neighbors[i]]

        # Center neighborhood around its centroid
        centroid = np.mean(neighbor_points, axis=0)
        centered = neighbor_points - centroid

        # 3x3 covariance matrix
        covariance = centered.T @ centered / k

        # Eigenvectors of covariance matrix
        eigenvalues, eigenvectors = np.linalg.eigh(covariance)

        # Smallest eigenvalue direction is normal to local best-fit plane
        normal = eigenvectors[:, np.argmin(eigenvalues)]

        # Normalize, just in case
        norm = np.linalg.norm(normal)
        if norm > 1e-12:
            normal = normal / norm

        normals[i] = normal

    return normals


def normal_wireframe(
    points: NDArray[np.float64],
    normals: NDArray[np.float64],
    *,
    length: float = NORMAL_LENGTH,
) -> Wireframe3:
    points = np.asarray(points, dtype=np.float64)
    normals = np.asarray(normals, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError("points must be an Nx3 array")
    if normals.shape != points.shape:
        raise ValueError("normals must match points shape")
    if length <= 0.0:
        raise ValueError("length must be positive")

    vertices_array = np.empty((points.shape[0] * 2, 3), dtype=np.float64)
    vertices_array[0::2] = points
    vertices_array[1::2] = points + normals * length
    vertices = tuple((float(x), float(y), float(z)) for x, y, z in vertices_array)
    edges = tuple((index, index + 1) for index in range(0, len(vertices), 2))
    return Wireframe3.from_edges(vertices, edges)

if __name__ == "__main__":
    node_points = points_from_dxf(LINESPLAN_DXF)
    cloud = PointCloud3(node_points)

    points = np.asarray(node_points, dtype=np.float64)

    normals = pca_normals(points, k=10)
    normal_lines = normal_wireframe(points, normals)

    scene = (
        Scene("linesplan intersection normals")
        .add(
            cloud,
            name="intersection_nodes",
            style=DisplayStyle(color=(0, 0, 1), render_mode="points", point_size=7.0),
        )
        .add(
            normal_lines,
            name="normal_lines",
            style=DisplayStyle(color=(1, 0, 0), render_mode="wireframe", line_width=1.0),
        )
    )

    from cady.view import view_scene

    view_scene(scene, title="linesplan intersection normals")
