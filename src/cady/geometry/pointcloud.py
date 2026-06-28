"""Unconnected point collections with transform support."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

from cady.operations.transforms import Transform2, Transform3
from cady.utils import positive_tolerance

Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]

if TYPE_CHECKING:
    import numpy as np

    from cady.view import Camera, DisplayStyle, Light
    from cady.view.open_view import Projection
    from cady.view.style import RenderMode


@dataclass(frozen=True, slots=True, init=False)
class PointCloud2:
    """Unconnected 2D point data."""

    vertices: tuple[Point2, ...]

    def __init__(self, vertices: Iterable[Point2]) -> None:
        object.__setattr__(self, "vertices", tuple(vertices))

    def bounds(self) -> tuple[Point2, Point2]:
        if not self.vertices:
            raise ValueError("cannot calculate bounds for an empty point cloud")
        return (
            (
                min(vertex[0] for vertex in self.vertices),
                min(vertex[1] for vertex in self.vertices),
            ),
            (
                max(vertex[0] for vertex in self.vertices),
                max(vertex[1] for vertex in self.vertices),
            ),
        )

    @property
    def boundary(self) -> tuple[Point2, Point2]:
        return self.bounds()

    def points(self) -> tuple[Point2, ...]:
        return self.vertices

    def to_array(self, *, tolerance: float) -> np.ndarray:
        positive_tolerance(tolerance)
        import numpy as np

        if not self.vertices:
            return np.empty((0, 2), dtype=np.float64)
        return np.array(self.vertices, dtype=np.float64)

    def transformed(self, transform: Transform2) -> PointCloud2:
        array = transform.apply_points(self.vertices)
        return PointCloud2((float(x), float(y)) for x, y in array)

    def mirror(self, point: object, direction: object) -> PointCloud2:
        return self.transformed(Transform2.mirror(point, direction))


@dataclass(frozen=True, slots=True, init=False)
class PointCloud3:
    """Unconnected 3D point data."""

    vertices: tuple[Point3, ...]

    def __init__(self, vertices: Iterable[Point3]) -> None:
        object.__setattr__(self, "vertices", tuple(vertices))

    def bounds(self) -> tuple[Point3, Point3]:
        if not self.vertices:
            raise ValueError("cannot calculate bounds for an empty point cloud")
        return (
            (
                min(vertex[0] for vertex in self.vertices),
                min(vertex[1] for vertex in self.vertices),
                min(vertex[2] for vertex in self.vertices),
            ),
            (
                max(vertex[0] for vertex in self.vertices),
                max(vertex[1] for vertex in self.vertices),
                max(vertex[2] for vertex in self.vertices),
            ),
        )

    @property
    def boundary(self) -> tuple[Point3, Point3]:
        return self.bounds()

    def points(self) -> tuple[Point3, ...]:
        return self.vertices

    def to_array(self, *, tolerance: float) -> np.ndarray:
        positive_tolerance(tolerance)
        import numpy as np

        if not self.vertices:
            return np.empty((0, 3), dtype=np.float64)
        return np.array(self.vertices, dtype=np.float64)

    def transformed(self, transform: Transform3) -> PointCloud3:
        array = transform.apply_points(self.vertices)
        return PointCloud3((float(x), float(y), float(z)) for x, y, z in array)

    def mirror(self, plane_origin: object, plane_normal: object) -> PointCloud3:
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


__all__ = ["PointCloud2", "PointCloud3"]
