from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from math import cos, sin
from typing import Any, Literal, TypeAlias, cast

from cad.geom.vec import Vec2, Vec3, promote2, promote3

AxisString: TypeAlias = Literal["+x", "-x", "+y", "-y", "+z", "-z"]
Axis: TypeAlias = AxisString | Vec3 | tuple[float, float, float]


def parse_axis(axis: Axis) -> AxisString | Vec3:
    if isinstance(axis, str):
        if axis not in {"+x", "-x", "+y", "-y", "+z", "-z"}:
            raise ValueError(f"unknown axis string {axis!r}")
        return axis
    return promote3(axis).normalised()


def axis_vector(axis: Axis) -> Vec3:
    parsed = parse_axis(axis)
    if isinstance(parsed, Vec3):
        return parsed
    vectors = {
        "+x": Vec3(1, 0, 0),
        "-x": Vec3(-1, 0, 0),
        "+y": Vec3(0, 1, 0),
        "-y": Vec3(0, -1, 0),
        "+z": Vec3(0, 0, 1),
        "-z": Vec3(0, 0, -1),
    }
    return vectors[parsed]


class Shape2D(ABC):
    closed: bool
    inner_loops: tuple[Shape2D, ...]

    @abstractmethod
    def bounds(self) -> tuple[Vec2, Vec2]: ...

    @abstractmethod
    def points(self) -> tuple[Vec2, ...]: ...

    @abstractmethod
    def close(self) -> Shape2D: ...

    @abstractmethod
    def _transform2(self, fn: Callable[[Vec2], Vec2]) -> Shape2D: ...

    def __add__(self, other: Shape2D) -> Shape2D:
        from cad.geom.shapes2d import Path

        return Path.from_shapes(self, other)

    def __sub__(self, other: Shape2D) -> Shape2D:
        raise TypeError("2D holes use with_hole(...); 3D booleans are deferred to the Stage 6 spec")

    def translate(self, dx: float, dy: float) -> Shape2D:
        offset = Vec2(dx, dy)
        return self._transform2(lambda point: point + offset)

    def rotate(self, centre: Vec2 | tuple[float, float], angle: float) -> Shape2D:
        c = promote2(centre)
        ca = cos(angle)
        sa = sin(angle)

        def rot(point: Vec2) -> Vec2:
            rel = point - c
            return Vec2(c.x + rel.x * ca - rel.y * sa, c.y + rel.x * sa + rel.y * ca)

        return self._transform2(rot)

    def scale(
        self,
        sx: float,
        sy: float | None = None,
        centre: Vec2 | tuple[float, float] = (0.0, 0.0),
    ) -> Shape2D:
        c = promote2(centre)
        y_scale = sx if sy is None else sy
        return self._transform2(lambda p: Vec2(c.x + (p.x - c.x) * sx, c.y + (p.y - c.y) * y_scale))

    def mirror(self, through: Shape2D) -> Shape2D:
        pts = through.points()
        if len(pts) < 2 or pts[0] == pts[-1]:
            raise ValueError("mirror axis must have two distinct points")
        a, b = pts[0], pts[-1]
        axis = (b - a).normalised()

        def reflect(point: Vec2) -> Vec2:
            rel = point - a
            projected = a + axis * rel.dot(axis)
            return projected * 2 - point

        return self._transform2(reflect)

    def with_hole(self, hole: Shape2D) -> Shape2D:
        return self.with_holes((hole,))

    def with_holes(self, holes: tuple[Shape2D, ...] | list[Shape2D]) -> Shape2D:
        if not self.closed:
            raise ValueError("with_hole requires a closed outer Shape2D")
        for hole in holes:
            if not hole.closed:
                raise ValueError("with_hole requires closed inner Shape2D loops")
        from dataclasses import replace

        return cast(
            Shape2D,
            replace(cast(Any, self), inner_loops=tuple(self.inner_loops) + tuple(holes)),
        )

    def extrude(self, axis: Axis, distance: float) -> Shape3D:
        from cad.geom.shapes3d import Extrusion

        return Extrusion(self, parse_axis(axis), distance)

    def revolve(
        self,
        axis: Shape2D | tuple[Vec3 | tuple[float, float, float], Vec3 | tuple[float, float, float]],
        angle: float = 6.283185307179586,
    ) -> Shape3D:
        from cad.geom.shapes3d import Revolution

        if isinstance(axis, tuple):
            origin = promote3(axis[0])
            direction = promote3(axis[1])
        else:
            pts = axis.points()
            if len(pts) < 2:
                raise ValueError("revolve axis must expose two points")
            origin = Vec3(pts[0].x, pts[0].y, 0.0)
            end = Vec3(pts[-1].x, pts[-1].y, 0.0)
            direction = end - origin
        return Revolution(self, origin, direction, angle)


class Shape3D(ABC):
    @abstractmethod
    def bounds(self) -> tuple[Vec3, Vec3]: ...

    @abstractmethod
    def _transform3(self, fn: Callable[[Vec3], Vec3]) -> Shape3D: ...

    def __sub__(self, other: Shape3D) -> Shape3D:
        raise TypeError(
            "3D boolean cut/union/intersect operations are deferred to the Stage 6 spec"
        )

    def translate(self, dx: float, dy: float, dz: float) -> Shape3D:
        offset = Vec3(dx, dy, dz)
        return self._transform3(lambda point: point + offset)

    def rotate(
        self,
        axis_origin: Vec3 | tuple[float, float, float],
        axis_dir: Vec3 | tuple[float, float, float],
        angle: float,
    ) -> Shape3D:
        origin = promote3(axis_origin)
        direction = promote3(axis_dir).normalised()
        ca = cos(angle)
        sa = sin(angle)

        def rot(point: Vec3) -> Vec3:
            rel = point - origin
            return (
                origin
                + rel * ca
                + direction.cross(rel) * sa
                + direction * (direction.dot(rel) * (1 - ca))
            )

        return self._transform3(rot)

    def mirror(
        self,
        plane_origin: Vec3 | tuple[float, float, float],
        plane_normal: Vec3 | tuple[float, float, float],
    ) -> Shape3D:
        origin = promote3(plane_origin)
        normal = promote3(plane_normal).normalised()
        return self._transform3(lambda p: p - normal * (2 * (p - origin).dot(normal)))
