"""Immutable 2D and 3D vector values."""

from __future__ import annotations

from math import sqrt
from typing import cast, overload

from cady.geometry.point import coordinate_values, tuple_value


class Vector2(tuple[float, float]):
    """Immutable 2D vector with tuple-compatible coordinate access."""

    @overload
    def __new__(cls, x: object, y: object) -> Vector2: ...

    @overload
    def __new__(cls, x: object, y: None = None) -> Vector2: ...

    def __new__(cls, x: object, y: object | None = None) -> Vector2:
        values = coordinate_values("Vector2", x, y, expected=2)
        return cast(Vector2, tuple_value(cls, values))

    @property
    def x(self) -> float:
        return self[0]

    @property
    def y(self) -> float:
        return self[1]

    @property
    def length(self) -> float:
        return sqrt(self.x * self.x + self.y * self.y)

    def normalised(self) -> Vector2:
        length = self.length
        if length == 0.0:
            raise ValueError("cannot normalise zero Vector2")
        return Vector2(self.x / length, self.y / length)

    def scaled(self, scalar: float) -> Vector2:
        value = float(scalar)
        return Vector2(self.x * value, self.y * value)


class Vector3(tuple[float, float, float]):
    """Immutable 3D vector with tuple-compatible coordinate access."""

    @overload
    def __new__(cls, x: object, y: object, z: object) -> Vector3: ...

    @overload
    def __new__(cls, x: object, y: None = None, z: None = None) -> Vector3: ...

    def __new__(
        cls,
        x: object,
        y: object | None = None,
        z: object | None = None,
    ) -> Vector3:
        values = coordinate_values("Vector3", x, y, z, expected=3)
        return cast(Vector3, tuple_value(cls, values))

    @property
    def x(self) -> float:
        return self[0]

    @property
    def y(self) -> float:
        return self[1]

    @property
    def z(self) -> float:
        return self[2]

    @property
    def length(self) -> float:
        return sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def normalised(self) -> Vector3:
        length = self.length
        if length == 0.0:
            raise ValueError("cannot normalise zero Vector3")
        return Vector3(self.x / length, self.y / length, self.z / length)

    def scaled(self, scalar: float) -> Vector3:
        value = float(scalar)
        return Vector3(self.x * value, self.y * value, self.z * value)


__all__ = ["Vector2", "Vector3"]
