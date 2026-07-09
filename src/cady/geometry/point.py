"""Immutable 2D and 3D point values."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from math import isfinite
from typing import TYPE_CHECKING, cast, overload

if TYPE_CHECKING:
    from cady.geometry.vector import Vector2, Vector3


class Point2(tuple[float, float]):
    """Immutable 2D point with tuple-compatible coordinate access."""

    @overload
    def __new__(cls, x: object, y: object) -> Point2: ...

    @overload
    def __new__(cls, x: object, y: None = None) -> Point2: ...

    def __new__(cls, x: object, y: object | None = None) -> Point2:
        values = coordinate_values("Point2", x, y, expected=2)
        return cast(Point2, tuple_value(cls, values))

    @property
    def x(self) -> float:
        return self[0]

    @property
    def y(self) -> float:
        return self[1]

    def translated(self, vector: object) -> Point2:
        from cady.geometry.vector import Vector2

        offset = Vector2(vector)
        return Point2(self.x + offset.x, self.y + offset.y)

    def vector_to(self, other: object) -> Vector2:
        from cady.geometry.vector import Vector2

        point = Point2(other)
        return Vector2(point.x - self.x, point.y - self.y)


class Point3(tuple[float, float, float]):
    """Immutable 3D point with tuple-compatible coordinate access."""

    @overload
    def __new__(cls, x: object, y: object, z: object) -> Point3: ...

    @overload
    def __new__(cls, x: object, y: None = None, z: None = None) -> Point3: ...

    def __new__(
        cls,
        x: object,
        y: object | None = None,
        z: object | None = None,
    ) -> Point3:
        values = coordinate_values("Point3", x, y, z, expected=3)
        return cast(Point3, tuple_value(cls, values))

    @property
    def x(self) -> float:
        return self[0]

    @property
    def y(self) -> float:
        return self[1]

    @property
    def z(self) -> float:
        return self[2]

    def translated(self, vector: object) -> Point3:
        from cady.geometry.vector import Vector3

        offset = Vector3(vector)
        return Point3(self.x + offset.x, self.y + offset.y, self.z + offset.z)

    def vector_to(self, other: object) -> Vector3:
        from cady.geometry.vector import Vector3

        point = Point3(other)
        return Vector3(point.x - self.x, point.y - self.y, point.z - self.z)


def coordinate_values(name: str, *values: object, expected: int) -> tuple[float, ...]:
    provided: tuple[object, ...] = tuple(value for value in values if value is not None)
    if len(provided) == 1 and _is_iterable_coordinate(provided[0]):
        provided = tuple(cast(Iterable[object], provided[0]))
    if len(provided) != expected:
        raise ValueError(f"{name} requires {expected} coordinates")

    coordinates: list[float] = []
    for index, value in enumerate(provided):
        try:
            coordinate = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise TypeError(f"{name} coordinate {index} must be a real number") from exc
        if not isfinite(coordinate):
            raise ValueError(f"{name} coordinate {index} must be finite")
        coordinates.append(coordinate)
    return tuple(coordinates)


def tuple_value(cls: type[object], values: Iterable[float]) -> object:
    factory = cast(
        Callable[[type[object], Iterable[float]], object],
        object.__getattribute__(tuple, "__new__"),
    )
    return factory(cls, values)


def _is_iterable_coordinate(value: object) -> bool:
    return not isinstance(value, str | bytes) and isinstance(value, Iterable)


__all__ = ["Point2", "Point3"]
