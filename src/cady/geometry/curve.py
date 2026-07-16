"""Common protocols for semantic 2D and 3D curves."""

from collections.abc import Sequence
from typing import Protocol, TypeAlias

Point2: TypeAlias = Sequence[float]
Point3: TypeAlias = Sequence[float]


class Curve2(Protocol):
    """Common protocol for 2D curves that can be discretized on demand."""

    def bounds(self) -> tuple[Point2, Point2]: ...

    def points(self) -> tuple[Point2, ...]: ...


class Curve3(Protocol):
    """Common protocol for 3D curves that can be sampled to polylines."""

    def bounds(self) -> tuple[Point3, Point3]: ...

    def points(self) -> tuple[Point3, ...]: ...


__all__ = ["Curve2", "Curve3"]
