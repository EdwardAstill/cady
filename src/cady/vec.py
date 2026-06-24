from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Self, cast


def _finite(value: float, name: str) -> float:
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


@dataclass(frozen=True, slots=True)
class Vec2:
    x: float
    y: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", _finite(self.x, "x"))
        object.__setattr__(self, "y", _finite(self.y, "y"))

    @classmethod
    def from_xy(cls, value: Vec2 | tuple[float, float]) -> Self:
        if isinstance(value, Vec2):
            return cls(value.x, value.y)
        if len(value) != 2:
            raise ValueError("Vec2 tuple must have exactly 2 values")
        return cls(value[0], value[1])

    def __iter__(self) -> Iterable[float]:
        yield self.x
        yield self.y

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Vec2):
            return self.x == other.x and self.y == other.y
        if isinstance(other, tuple):
            values = cast(tuple[float, ...], other)
            if len(values) != 2:
                return False
            return self.x == float(values[0]) and self.y == float(values[1])
        return NotImplemented

    def __add__(self, other: Vec2) -> Vec2:
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Vec2) -> Vec2:
        return Vec2(self.x - other.x, self.y - other.y)

    def __neg__(self) -> Vec2:
        return Vec2(-self.x, -self.y)

    def __mul__(self, scalar: float) -> Vec2:
        return Vec2(self.x * scalar, self.y * scalar)

    __rmul__ = __mul__

    def dot(self, other: Vec2) -> float:
        return self.x * other.x + self.y * other.y

    def length(self) -> float:
        return sqrt(self.dot(self))

    def normalised(self) -> Vec2:
        length = self.length()
        if length == 0:
            raise ValueError("cannot normalise zero Vec2")
        return self * (1.0 / length)

    def tuple(self) -> tuple[float, float]:
        return (self.x, self.y)


@dataclass(frozen=True, slots=True)
class Vec3:
    x: float
    y: float
    z: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", _finite(self.x, "x"))
        object.__setattr__(self, "y", _finite(self.y, "y"))
        object.__setattr__(self, "z", _finite(self.z, "z"))

    @classmethod
    def from_xyz(cls, value: Vec3 | tuple[float, float, float]) -> Self:
        if isinstance(value, Vec3):
            return cls(value.x, value.y, value.z)
        if len(value) != 3:
            raise ValueError("Vec3 tuple must have exactly 3 values")
        return cls(value[0], value[1], value[2])

    def __iter__(self) -> Iterable[float]:
        yield self.x
        yield self.y
        yield self.z

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Vec3):
            return self.x == other.x and self.y == other.y and self.z == other.z
        if isinstance(other, tuple):
            values = cast(tuple[float, ...], other)
            if len(values) != 3:
                return False
            return (
                self.x == float(values[0])
                and self.y == float(values[1])
                and self.z == float(values[2])
            )
        return NotImplemented

    def __add__(self, other: Vec3) -> Vec3:
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Vec3) -> Vec3:
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __neg__(self) -> Vec3:
        return Vec3(-self.x, -self.y, -self.z)

    def __mul__(self, scalar: float) -> Vec3:
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    __rmul__ = __mul__

    def dot(self, other: Vec3) -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: Vec3) -> Vec3:
        return Vec3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def length(self) -> float:
        return sqrt(self.dot(self))

    def normalised(self) -> Vec3:
        length = self.length()
        if length == 0:
            raise ValueError("cannot normalise zero Vec3")
        return self * (1.0 / length)

    def tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def is_parallel(self, other: Vec3, *, tol: float = 1e-6) -> bool:
        c = self.cross(other)
        return c.dot(c) < tol * tol

    def distance_to_line(self, line_point: Vec3, line_dir: Vec3) -> float:
        d = self - line_point
        c = d.cross(line_dir)
        return c.length() / line_dir.length()

    def project_onto_line(self, line_point: Vec3, line_dir: Vec3) -> float:
        d = self - line_point
        return d.dot(line_dir) / line_dir.dot(line_dir)


def promote2(value: Vec2 | tuple[float, float]) -> Vec2:
    return Vec2.from_xy(value)


def promote3(value: Vec3 | tuple[float, float, float]) -> Vec3:
    return Vec3.from_xyz(value)


__all__ = ["Vec2", "Vec3", "promote2", "promote3"]
