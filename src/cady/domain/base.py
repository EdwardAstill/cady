from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Literal, TypeAlias, cast

from cady.domain.vec import Vec2, Vec3, promote3

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

    @abstractmethod
    def to_array(self, *, tolerance: float = 1e-3) -> object: ...

    def visualise(self, *, tolerance: float = 1e-3) -> None:
        """Open an interactive 3D viewer for this shape."""
        from cady.visualisation.vispy_viewer import vispy_view_mesh

        vispy_view_mesh(self.to_array(tolerance=tolerance))

    def map_points(self, fn: Callable[[Vec2], Vec2]) -> Shape2D:
        return self._transform2(fn)

    def __add__(self, other: Shape2D) -> Shape2D:
        from cady.domain.shapes2d import Path

        return Path.from_shapes(self, other)

    def __sub__(self, other: Shape2D) -> Shape2D:
        raise TypeError("2D holes use with_hole(...); 3D booleans are deferred to the Stage 6 spec")

    def translate(self, dx: float, dy: float) -> Shape2D:
        from cady.ops.transforms import translate2

        return translate2(self, dx, dy)

    def rotate(self, centre: Vec2 | tuple[float, float], angle: float) -> Shape2D:
        from cady.ops.transforms import rotate2

        return rotate2(self, centre, angle)

    def scale(
        self,
        sx: float,
        sy: float | None = None,
        centre: Vec2 | tuple[float, float] = (0.0, 0.0),
    ) -> Shape2D:
        from cady.ops.transforms import scale2

        return scale2(self, sx, sy, centre)

    def mirror(self, through: Shape2D) -> Shape2D:
        from cady.ops.transforms import mirror2

        return mirror2(self, through)

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
        from cady.domain.shapes3d import Extrusion

        return Extrusion(self, parse_axis(axis), distance)

    def revolve(
        self,
        axis: Shape2D | tuple[Vec3 | tuple[float, float, float], Vec3 | tuple[float, float, float]],
        angle: float = 6.283185307179586,
    ) -> Shape3D:
        from cady.domain.shapes3d import Revolution

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

    @abstractmethod
    def to_array(self, *, tolerance: float = 1e-3) -> object: ...

    def visualise(self, *, tolerance: float = 1e-3) -> None:
        """Open an interactive 3D viewer for this shape."""
        from cady.visualisation.vispy_viewer import vispy_view_mesh

        vispy_view_mesh(self.to_array(tolerance=tolerance))

    def map_points(self, fn: Callable[[Vec3], Vec3]) -> Shape3D:
        return self._transform3(fn)

    def __sub__(self, other: Shape3D) -> Shape3D:
        raise TypeError(
            "3D boolean cut/union/intersect operations are deferred to the Stage 6 spec"
        )

    def translate(self, dx: float, dy: float, dz: float) -> Shape3D:
        from cady.ops.transforms import translate3

        return translate3(self, dx, dy, dz)

    def rotate(
        self,
        axis_origin: Vec3 | tuple[float, float, float],
        axis_dir: Vec3 | tuple[float, float, float],
        angle: float,
    ) -> Shape3D:
        from cady.ops.transforms import rotate3

        return rotate3(self, axis_origin, axis_dir, angle)

    def mirror(
        self,
        plane_origin: Vec3 | tuple[float, float, float],
        plane_normal: Vec3 | tuple[float, float, float],
    ) -> Shape3D:
        from cady.ops.transforms import mirror3

        return mirror3(self, plane_origin, plane_normal)
