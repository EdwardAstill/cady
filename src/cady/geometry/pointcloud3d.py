from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cady.geometry.polyline3d import Point3Like
from cady.operations.transforms import Transform3
from cady.utils import positive_tolerance
from cady.vec import Vec3, promote3

if TYPE_CHECKING:
    import numpy as np

    from cady.view import Camera, DisplayStyle, Light
    from cady.view.open_view import Projection
    from cady.view.style import RenderMode


@dataclass(frozen=True, slots=True, init=False)
class PointCloud3D:
    """Unconnected 3D point data."""

    vertices: tuple[Vec3, ...]

    def __init__(self, vertices: Iterable[Point3Like]) -> None:
        object.__setattr__(self, "vertices", tuple(promote3(point) for point in vertices))

    def bounds(self) -> tuple[Vec3, Vec3]:
        if not self.vertices:
            raise ValueError("cannot calculate bounds for an empty point cloud")
        return (
            Vec3(
                min(vertex.x for vertex in self.vertices),
                min(vertex.y for vertex in self.vertices),
                min(vertex.z for vertex in self.vertices),
            ),
            Vec3(
                max(vertex.x for vertex in self.vertices),
                max(vertex.y for vertex in self.vertices),
                max(vertex.z for vertex in self.vertices),
            ),
        )

    def points(self) -> tuple[Vec3, ...]:
        return self.vertices

    def to_array(self, *, tolerance: float) -> np.ndarray:
        positive_tolerance(tolerance)
        import numpy as np

        if not self.vertices:
            return np.empty((0, 3), dtype=np.float64)
        return np.array([vertex.tuple() for vertex in self.vertices], dtype=np.float64)

    def transformed(self, transform: Transform3) -> PointCloud3D:
        array = transform.apply_points([vertex.tuple() for vertex in self.vertices])
        return PointCloud3D(Vec3(float(x), float(y), float(z)) for x, y, z in array)

    def mirror(self, plane_origin: object, plane_normal: object) -> PointCloud3D:
        return self.transformed(Transform3.mirror(plane_origin, plane_normal))

    def view(
        self,
        *,
        name: str | None = None,
        title: str | None = None,
        camera: Camera | None = None,
        style: DisplayStyle | None = None,
        light: Light | None = None,
        color: tuple[float, float, float] | None = None,
        render_mode: RenderMode | None = None,
        projection: Projection = "orthographic",
        center: bool = True,
        tolerance: float = 1e-3,
    ) -> None:
        from cady.view.open_view import open_target_view

        open_target_view(
            self,
            name=name,
            title=title,
            camera=camera,
            style=style,
            light=light,
            color=color,
            render_mode=render_mode or "points",
            projection=projection,
            center=center,
            tolerance=tolerance,
        )


__all__ = ["PointCloud3D"]
