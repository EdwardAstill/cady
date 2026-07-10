"""Immutable 2D and 3D displacement vectors."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from math import sqrt
from numbers import Real
from types import NotImplementedType
from typing import cast, overload

from cady.geometry._coordinates import finite_coordinates
from cady.utils import finite


@dataclass(frozen=True, init=False)
class Vector2(Sequence[float]):
    """Immutable 2D direction or displacement."""

    _coordinates: tuple[float, float] = field(repr=False)

    def __init__(self, x: object, y: object) -> None:
        values = finite_coordinates((x, y), expected=2, name="Vector2")
        object.__setattr__(self, "_coordinates", cast(tuple[float, float], values))

    @property
    def x(self) -> float:
        return self._coordinates[0]

    @property
    def y(self) -> float:
        return self._coordinates[1]

    @property
    def length(self) -> float:
        return sqrt(self.x * self.x + self.y * self.y)

    def normalized(self) -> Vector2:
        length = self.length
        if length == 0.0:
            raise ValueError("cannot normalize a zero vector")
        return self / length

    def dot(self, other: Vector2) -> float:
        if not isinstance(cast(object, other), Vector2):
            raise TypeError("dot requires another Vector2")
        return self.x * other.x + self.y * other.y

    def __add__(self, other: Vector2) -> Vector2 | NotImplementedType:
        if not isinstance(cast(object, other), Vector2):
            return NotImplemented
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Vector2) -> Vector2 | NotImplementedType:
        if not isinstance(cast(object, other), Vector2):
            return NotImplemented
        return Vector2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> Vector2 | NotImplementedType:
        if not isinstance(cast(object, scalar), Real) or isinstance(scalar, bool):
            return NotImplemented
        value = finite(scalar, "scalar")
        return Vector2(self.x * value, self.y * value)

    def __rmul__(self, scalar: float) -> Vector2 | NotImplementedType:
        return self * scalar

    def __truediv__(self, scalar: float) -> Vector2 | NotImplementedType:
        if not isinstance(cast(object, scalar), Real) or isinstance(scalar, bool):
            return NotImplemented
        value = finite(scalar, "scalar")
        if value == 0.0:
            raise ZeroDivisionError("cannot divide a vector by zero")
        return Vector2(self.x / value, self.y / value)

    def __neg__(self) -> Vector2:
        return Vector2(-self.x, -self.y)

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
        return f"Vector2(x={self.x!r}, y={self.y!r})"

    def __eq__(self, other: object) -> bool | NotImplementedType:
        if isinstance(other, Vector2):
            return self._coordinates == other._coordinates
        if isinstance(other, tuple):
            return self._coordinates == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._coordinates)


@dataclass(frozen=True, init=False)
class Vector3(Sequence[float]):
    """Immutable 3D direction or displacement."""

    _coordinates: tuple[float, float, float] = field(repr=False)

    def __init__(self, x: object, y: object, z: object) -> None:
        values = finite_coordinates((x, y, z), expected=3, name="Vector3")
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

    @property
    def length(self) -> float:
        return sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def normalized(self) -> Vector3:
        length = self.length
        if length == 0.0:
            raise ValueError("cannot normalize a zero vector")
        return self / length

    def dot(self, other: Vector3) -> float:
        if not isinstance(cast(object, other), Vector3):
            raise TypeError("dot requires another Vector3")
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: Vector3) -> Vector3:
        if not isinstance(cast(object, other), Vector3):
            raise TypeError("cross requires another Vector3")
        return Vector3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def __add__(self, other: Vector3) -> Vector3 | NotImplementedType:
        if not isinstance(cast(object, other), Vector3):
            return NotImplemented
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Vector3) -> Vector3 | NotImplementedType:
        if not isinstance(cast(object, other), Vector3):
            return NotImplemented
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> Vector3 | NotImplementedType:
        if not isinstance(cast(object, scalar), Real) or isinstance(scalar, bool):
            return NotImplemented
        value = finite(scalar, "scalar")
        return Vector3(self.x * value, self.y * value, self.z * value)

    def __rmul__(self, scalar: float) -> Vector3 | NotImplementedType:
        return self * scalar

    def __truediv__(self, scalar: float) -> Vector3 | NotImplementedType:
        if not isinstance(cast(object, scalar), Real) or isinstance(scalar, bool):
            return NotImplemented
        value = finite(scalar, "scalar")
        if value == 0.0:
            raise ZeroDivisionError("cannot divide a vector by zero")
        return Vector3(self.x / value, self.y / value, self.z / value)

    def __neg__(self) -> Vector3:
        return Vector3(-self.x, -self.y, -self.z)

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
        return f"Vector3(x={self.x!r}, y={self.y!r}, z={self.z!r})"

    def __eq__(self, other: object) -> bool | NotImplementedType:
        if isinstance(other, Vector3):
            return self._coordinates == other._coordinates
        if isinstance(other, tuple):
            return self._coordinates == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._coordinates)


__all__ = ["Vector2", "Vector3"]
