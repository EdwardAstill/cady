from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from cady.geometry.curves2d import Circle2D, ClosedCurve2D, ClosedPolyline2D, Point2Like
from cady.vec import Vec2

if TYPE_CHECKING:
    from cady.operations import ArrayPolygon2


@dataclass(frozen=True, slots=True)
class Profile2D:
    outer: ClosedCurve2D
    holes: tuple[ClosedCurve2D, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "holes", tuple(self.holes))

    @classmethod
    def rectangle(
        cls,
        width: float,
        height: float,
        *,
        origin: Point2Like = (0.0, 0.0),
    ) -> Profile2D:
        return cls(_rectangle_boundary(width, height, origin=origin))

    @classmethod
    def circle(cls, radius: float, *, centre: Point2Like = (0.0, 0.0)) -> Profile2D:
        return cls(Circle2D(centre, radius))

    def bounds(self) -> tuple[Vec2, Vec2]:
        return self.outer.bounds()

    def points(self) -> tuple[Vec2, ...]:
        return self.outer.points()

    def to_array(self, *, tolerance: float) -> ArrayPolygon2:
        from cady.operations import ArrayPolygon2

        outer = self.outer.to_array(tolerance=tolerance)
        hole_arrays = tuple(hole.to_array(tolerance=tolerance) for hole in self.holes)
        return ArrayPolygon2(
            outer.outer,
            holes=outer.holes + tuple(hole.outer for hole in hole_arrays),
        )


def _rectangle_boundary(
    width: float,
    height: float,
    *,
    origin: Point2Like = (0.0, 0.0),
) -> ClosedPolyline2D:
    origin = Vec2.from_xy(origin)
    width = float(width)
    height = float(height)
    if width <= 0.0:
        raise ValueError("width must be positive")
    if height <= 0.0:
        raise ValueError("height must be positive")
    return ClosedPolyline2D(
        (
            origin,
            Vec2(origin.x + width, origin.y),
            Vec2(origin.x + width, origin.y + height),
            Vec2(origin.x, origin.y + height),
        )
    )
