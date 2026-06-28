"""Open and closed 2D polyline geometry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from cady.geometry.curves2 import (
    Point2Like,
    bounds_from_points,
    dedupe_closed,
    point_tuples,
    polygon_array,
    polyline_array,
    validate_tolerance,
)
from cady.utils import loop_edges
from cady.vec import Vec2, promote2

if TYPE_CHECKING:
    from cady.geometry.mesh2 import Mesh2
    from cady.operations import ArrayPolygon2, ArrayPolyline2


@dataclass(frozen=True, slots=True, init=False)
class Polyline2:
    """Open 2D path made from straight segments."""

    vertices: tuple[Vec2, ...]

    def __init__(self, vertices: tuple[Point2Like, ...]) -> None:
        vertices = tuple(promote2(point) for point in vertices)
        object.__setattr__(self, "vertices", vertices)
        if len(vertices) < 2:
            raise ValueError("Polyline2 requires at least two vertices")

    def bounds(self) -> tuple[Vec2, Vec2]:
        return bounds_from_points(self.vertices)

    def points(self) -> tuple[Vec2, ...]:
        return self.vertices

    def to_array(self, *, tolerance: float) -> ArrayPolyline2:
        validate_tolerance(tolerance)
        return polyline_array(self.vertices, closed=False)


@dataclass(frozen=True, slots=True, init=False)
class ClosedPolyline2:
    """Closed 2D boundary loop made from straight segments."""

    vertices: tuple[Vec2, ...]

    def __init__(self, vertices: tuple[Point2Like, ...]) -> None:
        vertices = dedupe_closed(tuple(promote2(point) for point in vertices))
        object.__setattr__(self, "vertices", vertices)
        if len(vertices) < 3:
            raise ValueError("ClosedPolyline2 requires at least three vertices")

    def bounds(self) -> tuple[Vec2, Vec2]:
        return bounds_from_points(self.vertices)

    def points(self) -> tuple[Vec2, ...]:
        return self.vertices + (self.vertices[0],)

    def to_array(self, *, tolerance: float) -> ArrayPolygon2:
        validate_tolerance(tolerance)
        return polygon_array(self.vertices)

    def to_mesh(self, *, tolerance: float) -> Mesh2:
        tolerance = validate_tolerance(tolerance)
        from cady.geometry.mesh2 import Mesh2
        from cady.operations.polygons2 import triangulate_polygon

        point_to_index = {point.tuple(): index for index, point in enumerate(self.vertices)}
        triangles = triangulate_polygon(point_tuples(self.vertices), tolerance=tolerance)
        faces = tuple(
            (
                point_to_index[a],
                point_to_index[b],
                point_to_index[c],
            )
            for a, b, c in triangles
        )
        return Mesh2(self.vertices, faces, loop_edges(len(self.vertices)))


__all__ = ["ClosedPolyline2", "Polyline2"]
