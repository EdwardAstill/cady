from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cady.errors import GeometryError
from cady.utils import loop_edges, positive_tolerance
from cady.vec import Vec3, promote3

if TYPE_CHECKING:
    from cady.geometry.mesh3d import Mesh3D
    from cady.operations.arrays3d import ArrayPolyline3


Point3Like = Vec3 | tuple[float, float, float]
FaceIndex = tuple[int, int, int]
EdgeIndex = tuple[int, int]


def _bounds(points: tuple[Vec3, ...]) -> tuple[Vec3, Vec3]:
    if not points:
        raise ValueError("bounds require at least one point")
    return (
        Vec3(
            min(point.x for point in points),
            min(point.y for point in points),
            min(point.z for point in points),
        ),
        Vec3(
            max(point.x for point in points),
            max(point.y for point in points),
            max(point.z for point in points),
        ),
    )


def _dedupe_closed(vertices: tuple[Vec3, ...]) -> tuple[Vec3, ...]:
    if len(vertices) > 1 and vertices[0] == vertices[-1]:
        return vertices[:-1]
    return vertices


def _unique_vertex_count(vertices: tuple[Vec3, ...]) -> int:
    return len({vertex.tuple() for vertex in vertices})


@dataclass(frozen=True, slots=True, init=False)
class Polyline3D:
    """Open 3D polyline/wire data."""

    vertices: tuple[Vec3, ...]

    def __init__(self, vertices: Iterable[Point3Like]) -> None:
        vertices = tuple(promote3(point) for point in vertices)
        object.__setattr__(self, "vertices", vertices)
        if len(vertices) < 2:
            raise ValueError("Polyline3D requires at least two vertices")

    def bounds(self) -> tuple[Vec3, Vec3]:
        return _bounds(self.vertices)

    def points(self) -> tuple[Vec3, ...]:
        return self.vertices

    def to_array(self, *, tolerance: float) -> ArrayPolyline3:
        positive_tolerance(tolerance)
        import numpy as np

        from cady.operations.arrays3d import ArrayPolyline3

        return ArrayPolyline3(
            np.array([vertex.tuple() for vertex in self.vertices], dtype=np.float64)
        )


@dataclass(frozen=True, slots=True, init=False)
class ClosedPolyline3D:
    """Planar closed 3D boundary loop."""

    vertices: tuple[Vec3, ...]

    def __init__(self, vertices: Iterable[Point3Like]) -> None:
        vertices = _dedupe_closed(tuple(promote3(point) for point in vertices))
        object.__setattr__(self, "vertices", vertices)
        if _unique_vertex_count(vertices) < 3:
            raise ValueError("ClosedPolyline3D requires at least three unique vertices")

    def bounds(self) -> tuple[Vec3, Vec3]:
        return _bounds(self.vertices)

    def points(self) -> tuple[Vec3, ...]:
        return self.vertices + (self.vertices[0],)

    def to_array(self, *, tolerance: float) -> ArrayPolyline3:
        positive_tolerance(tolerance)
        import numpy as np

        from cady.operations.arrays3d import ArrayPolyline3

        return ArrayPolyline3(
            np.array([vertex.tuple() for vertex in self.points()], dtype=np.float64)
        )

    def to_mesh(self, *, tolerance: float) -> Mesh3D:
        tolerance = positive_tolerance(tolerance)

        import numpy as np

        from cady.geometry.mesh3d import Mesh3D
        from cady.operations.mesh_caps import triangulate_loop
        from cady.operations.planes import fit_plane_svd, max_plane_deviation, project_loop

        vertex_arrays = [np.array(vertex.tuple(), dtype=np.float64) for vertex in self.vertices]
        loop_points = np.array(vertex_arrays, dtype=np.float64)
        origin, normal = fit_plane_svd(loop_points)
        deviation = max_plane_deviation(loop_points, origin, normal)
        if deviation > tolerance:
            raise GeometryError(
                f"closed polyline is non-planar (max deviation {deviation:.3e} > "
                f"tolerance {tolerance:.3e})"
            )

        loop = list(range(len(self.vertices)))
        projected = project_loop(loop, vertex_arrays, origin, normal)
        faces = tuple(triangulate_loop(projected, tolerance))
        return Mesh3D(self.vertices, faces, loop_edges(len(self.vertices)))


__all__ = ["ClosedPolyline3D", "Point3Like", "Polyline3D"]
