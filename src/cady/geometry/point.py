"""Immutable 2D and 3D affine points."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from types import NotImplementedType
from typing import cast, overload

from cady.geometry._coordinates import finite_coordinates
from cady.geometry.vector import Vector2, Vector3


@dataclass(frozen=True, init=False)
class Point2(Sequence[float]):
    """Immutable position in 2D space."""

    _coordinates: tuple[float, float] = field(repr=False)

    def __init__(self, x: object, y: object) -> None:
        values = finite_coordinates((x, y), expected=2, name="Point2")
        object.__setattr__(self, "_coordinates", cast(tuple[float, float], values))

    @property
    def x(self) -> float:
        return self._coordinates[0]

    @property
    def y(self) -> float:
        return self._coordinates[1]

    def __add__(self, vector: Vector2) -> Point2 | NotImplementedType:
        if not isinstance(cast(object, vector), Vector2):
            return NotImplemented
        return Point2(self.x + vector.x, self.y + vector.y)

    @overload
    def __sub__(self, other: Point2) -> Vector2: ...

    @overload
    def __sub__(self, other: Vector2) -> Point2: ...

    def __sub__(self, other: Point2 | Vector2) -> Point2 | Vector2 | NotImplementedType:
        value = cast(object, other)
        if isinstance(value, Point2):
            return Vector2(self.x - value.x, self.y - value.y)
        if isinstance(value, Vector2):
            return Point2(self.x - value.x, self.y - value.y)
        return NotImplemented

    def __iter__(self) -> Iterator[float]:
        return iter(self._coordinates)

    def __len__(self) -> int:
        return 2

    @overload
    def __getitem__(self, index: int) -> float: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[float, ...]: ...

    def __getitem__(self, index: int | slice) -> float | tuple[float, ...]:
        return self._coordinates[index]

    def __repr__(self) -> str:
        return f"Point2(x={self.x!r}, y={self.y!r})"

    def __eq__(self, other: object) -> bool | NotImplementedType:
        if isinstance(other, Point2):
            return self._coordinates == other._coordinates
        if isinstance(other, tuple):
            return self._coordinates == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._coordinates)


@dataclass(frozen=True, init=False)
class Point3(Sequence[float]):
    """Immutable position in 3D space."""

    _coordinates: tuple[float, float, float] = field(repr=False)

    def __init__(self, x: object, y: object, z: object) -> None:
        values = finite_coordinates((x, y, z), expected=3, name="Point3")
        object.__setattr__(self, "_coordinates", cast(tuple[float, float, float], values))

    @property
    def x(self) -> float:
        return self._coordinates[0]

    @property
    def y(self) -> float:
        return self._coordinates[1]

    @property
    def z(self) -> float:
        return self._coordinates[2]

    def __add__(self, vector: Vector3) -> Point3 | NotImplementedType:
        if not isinstance(cast(object, vector), Vector3):
            return NotImplemented
        return Point3(self.x + vector.x, self.y + vector.y, self.z + vector.z)

    @overload
    def __sub__(self, other: Point3) -> Vector3: ...

    @overload
    def __sub__(self, other: Vector3) -> Point3: ...

    def __sub__(self, other: Point3 | Vector3) -> Point3 | Vector3 | NotImplementedType:
        value = cast(object, other)
        if isinstance(value, Point3):
            return Vector3(self.x - value.x, self.y - value.y, self.z - value.z)
        if isinstance(value, Vector3):
            return Point3(self.x - value.x, self.y - value.y, self.z - value.z)
        return NotImplemented

    def __iter__(self) -> Iterator[float]:
        return iter(self._coordinates)

    def __len__(self) -> int:
        return 3

    @overload
    def __getitem__(self, index: int) -> float: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[float, ...]: ...

    def __getitem__(self, index: int | slice) -> float | tuple[float, ...]:
        return self._coordinates[index]

    def __repr__(self) -> str:
        return f"Point3(x={self.x!r}, y={self.y!r}, z={self.z!r})"

    def __eq__(self, other: object) -> bool | NotImplementedType:
        if isinstance(other, Point3):
            return self._coordinates == other._coordinates
        if isinstance(other, tuple):
            return self._coordinates == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._coordinates)


__all__ = ["Point2", "Point3"]
