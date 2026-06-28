"""2D and 3D parametric surface support types."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, TypeAlias

from cady.geometry.plane3 import Plane3
from cady.operations.coordinates import cross3, normalised2, normalised3, sub3

SurfaceKind = Literal["plane", "parametric"]
ScalarFunction = Callable[[float, float], float]
Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class Surface2:
    """Parametric 2D surface for planar parameter spaces."""

    x_function: ScalarFunction
    y_function: ScalarFunction
    kind: SurfaceKind

    @classmethod
    def parametric(cls, x: ScalarFunction, y: ScalarFunction) -> Surface2:
        return cls(x, y, "parametric")

    @classmethod
    def plane(
        cls,
        *,
        origin: Point2 = (0.0, 0.0),
        x_axis: Point2 = (1.0, 0.0),
    ) -> Surface2:
        x_axis = normalised2(x_axis)
        y_axis = (-x_axis[1], x_axis[0])
        return cls(
            lambda u, v: origin[0] + x_axis[0] * u + y_axis[0] * v,
            lambda u, v: origin[1] + x_axis[1] * u + y_axis[1] * v,
            "plane",
        )

    @classmethod
    def world_xy(cls) -> Surface2:
        return cls.plane()

    def point(self, u: float, v: float) -> Point2:
        u = float(u)
        v = float(v)
        return (float(self.x_function(u, v)), float(self.y_function(u, v)))


@dataclass(frozen=True, slots=True)
class Surface3:
    """Parametric 3D surface for bounded regions.

    The surface is defined by three scalar functions ``x(u, v)``, ``y(u, v)``,
    and ``z(u, v)``. Named constructors can provide analytic surfaces while
    retaining the same parametric interface.
    """

    x_function: ScalarFunction
    y_function: ScalarFunction
    z_function: ScalarFunction
    kind: SurfaceKind
    base_plane: Plane3 | None = None

    @classmethod
    def parametric(
        cls,
        x: ScalarFunction,
        y: ScalarFunction,
        z: ScalarFunction,
    ) -> Surface3:
        return cls(x, y, z, "parametric")

    @classmethod
    def plane(
        cls,
        *,
        plane: Plane3 | None = None,
        origin: Point3 = (0.0, 0.0, 0.0),
        normal: Point3 = (0.0, 0.0, 1.0),
        x_axis: Point3 | None = None,
    ) -> Surface3:
        base_plane = plane
        if base_plane is None:
            base_plane = Plane3.from_normal(
                origin,
                normal,
                x_axis=x_axis,
            )
        return cls(
            lambda u, v: base_plane.point(u, v)[0],
            lambda u, v: base_plane.point(u, v)[1],
            lambda u, v: base_plane.point(u, v)[2],
            "plane",
            base_plane=base_plane,
        )

    @classmethod
    def world_xy(cls) -> Surface3:
        return cls.plane(plane=Plane3.world_xy())

    def point(self, u: float, v: float) -> Point3:
        u = float(u)
        v = float(v)
        return (
            float(self.x_function(u, v)),
            float(self.y_function(u, v)),
            float(self.z_function(u, v)),
        )

    def normal(self, u: float, v: float) -> Point3:
        if self.kind == "plane" and self.base_plane is not None:
            return self.base_plane.normal
        step = 1e-6
        centre_u = float(u)
        centre_v = float(v)
        du = sub3(self.point(centre_u + step, centre_v), self.point(centre_u - step, centre_v))
        dv = sub3(self.point(centre_u, centre_v + step), self.point(centre_u, centre_v - step))
        return normalised3(cross3(du, dv))


__all__ = ["ScalarFunction", "Surface2", "Surface3", "SurfaceKind"]
