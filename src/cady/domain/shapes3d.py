from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from math import pi

from cady.domain.base import AxisString, Shape2D, Shape3D, parse_axis
from cady.domain.vec import Vec3, promote3


def _bounds(points: tuple[Vec3, ...]) -> tuple[Vec3, Vec3]:
    return (
        Vec3(min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)),
        Vec3(max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)),
    )


@dataclass(frozen=True, slots=True)
class Sphere(Shape3D):
    centre: Vec3
    radius: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "centre", promote3(self.centre))
        object.__setattr__(self, "radius", float(self.radius))
        if self.radius <= 0:
            raise ValueError("Sphere radius must be positive")

    def bounds(self) -> tuple[Vec3, Vec3]:
        r = self.radius
        return (self.centre - Vec3(r, r, r), self.centre + Vec3(r, r, r))

    def _transform3(self, fn: Callable[[Vec3], Vec3]) -> Shape3D:
        centre = fn(self.centre)
        edge = fn(self.centre + Vec3(self.radius, 0, 0))
        return Sphere(centre, (edge - centre).length())

    def to_array(self, *, tolerance: float = 1e-3) -> object:
        from cady.domain.mesh import triangles_to_array_mesh
        from cady.ops.tessellate import sphere_to_triangles

        return triangles_to_array_mesh(sphere_to_triangles(self, tolerance=tolerance))


@dataclass(frozen=True, slots=True)
class Prism(Shape3D):
    origin: Vec3
    size: Vec3

    def __post_init__(self) -> None:
        object.__setattr__(self, "origin", promote3(self.origin))
        object.__setattr__(self, "size", promote3(self.size))
        if self.size.x == 0 or self.size.y == 0 or self.size.z == 0:
            raise ValueError("Prism size components must be non-zero")

    def corners(self) -> tuple[Vec3, ...]:
        x0, y0, z0 = self.origin.x, self.origin.y, self.origin.z
        x1, y1, z1 = x0 + self.size.x, y0 + self.size.y, z0 + self.size.z
        return (
            Vec3(x0, y0, z0),
            Vec3(x1, y0, z0),
            Vec3(x1, y1, z0),
            Vec3(x0, y1, z0),
            Vec3(x0, y0, z1),
            Vec3(x1, y0, z1),
            Vec3(x1, y1, z1),
            Vec3(x0, y1, z1),
        )

    def bounds(self) -> tuple[Vec3, Vec3]:
        return _bounds(self.corners())

    def _transform3(self, fn: Callable[[Vec3], Vec3]) -> Shape3D:
        corners = tuple(fn(point) for point in self.corners())
        mn, mx = _bounds(corners)
        return Prism(mn, mx - mn)

    def to_array(self, *, tolerance: float = 1e-3) -> object:
        from cady.domain.mesh import triangles_to_array_mesh
        from cady.ops.tessellate import prism_to_triangles

        return triangles_to_array_mesh(prism_to_triangles(self))


@dataclass(frozen=True, slots=True)
class Extrusion(Shape3D):
    profile: Shape2D
    axis: AxisString | Vec3
    distance: float
    offset: Vec3 = Vec3(0, 0, 0)

    def __post_init__(self) -> None:
        if not self.profile.closed:
            raise ValueError("Extrusion profile must be closed")
        object.__setattr__(self, "axis", parse_axis(self.axis))
        object.__setattr__(self, "distance", float(self.distance))
        object.__setattr__(self, "offset", promote3(self.offset))
        if self.distance == 0:
            raise ValueError("Extrusion distance must be non-zero")

    def bounds(self) -> tuple[Vec3, Vec3]:
        from cady.ops.tessellate import extrusion_to_triangles

        return _bounds(
            tuple(point for tri in extrusion_to_triangles(self, tolerance=1e-2) for point in tri)
        )

    def _transform3(self, fn: Callable[[Vec3], Vec3]) -> Shape3D:
        return replace(self, offset=fn(self.offset))

    def to_array(self, *, tolerance: float = 1e-3) -> object:
        from cady.domain.mesh import triangles_to_array_mesh
        from cady.ops.tessellate import extrusion_to_triangles

        return triangles_to_array_mesh(extrusion_to_triangles(self, tolerance=tolerance))


@dataclass(frozen=True, slots=True)
class Revolution(Shape3D):
    profile: Shape2D
    axis_origin: Vec3
    axis_direction: Vec3
    angle_rad: float = 2 * pi

    def __post_init__(self) -> None:
        object.__setattr__(self, "axis_origin", promote3(self.axis_origin))
        object.__setattr__(self, "axis_direction", promote3(self.axis_direction).normalised())
        object.__setattr__(self, "angle_rad", float(self.angle_rad))
        if self.angle_rad == 0:
            raise ValueError("Revolution angle must be non-zero")

    def bounds(self) -> tuple[Vec3, Vec3]:
        from cady.ops.tessellate import revolution_to_triangles

        return _bounds(
            tuple(point for tri in revolution_to_triangles(self, tolerance=1e-2) for point in tri)
        )

    def _transform3(self, fn: Callable[[Vec3], Vec3]) -> Shape3D:
        return replace(self, axis_origin=fn(self.axis_origin))

    def to_array(self, *, tolerance: float = 1e-3) -> object:
        from cady.domain.mesh import triangles_to_array_mesh
        from cady.ops.tessellate import revolution_to_triangles

        return triangles_to_array_mesh(revolution_to_triangles(self, tolerance=tolerance))
