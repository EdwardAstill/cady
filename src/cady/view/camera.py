"""Camera definitions and validation for backend-independent scenes."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import acos, degrees, isfinite
from typing import Any, Literal, TypeAlias, cast

from cady.operations.coordinates import dot3, length3, sub3
from cady.view.errors import ViewError

Point3: TypeAlias = tuple[float, float, float]
Projection = Literal["perspective", "orthographic"]


def finite_point3(value: object, *, name: str = "point") -> Point3:
    """Coerce a tuple-like value into a finite 3D point."""
    as_tuple = getattr(value, "tuple", None)
    raw = as_tuple() if callable(as_tuple) else value
    try:
        point = tuple(float(component) for component in cast(Iterable[Any], raw))
    except (TypeError, ValueError) as exc:
        raise ViewError(f"{name} must be a finite 3D coordinate") from exc
    if len(point) != 3 or any(not isfinite(component) for component in point):
        raise ViewError(f"{name} must be a finite 3D coordinate")
    return (point[0], point[1], point[2])


def _reject_degenerate_basis(position: Point3, target: Point3, up: Point3) -> None:
    view = sub3(target, position)
    view_length = length3(view)
    up_length = length3(up)
    if view_length == 0.0:
        raise ViewError("camera position and target must be different")
    if up_length == 0.0:
        raise ViewError("camera up vector must be non-zero")
    cosine = abs(dot3(view, up) / (view_length * up_length))
    if degrees(acos(min(1.0, cosine))) < 1e-6:
        raise ViewError("camera up vector must not be parallel to the view direction")


@dataclass(frozen=True, slots=True)
class Camera:
    """Immutable camera description used by scene viewers."""

    position: Point3
    target: Point3
    up: Point3 = (0.0, 0.0, 1.0)
    projection: Projection = "perspective"
    fov_degrees: float = 45.0
    orthographic_scale: float = 1.0
    near: float = 1e-3
    far: float = 1e6
    min_distance: float | None = None
    max_distance: float | None = None
    min_orthographic_scale: float | None = None
    max_orthographic_scale: float | None = None

    def __post_init__(self) -> None:
        position = finite_point3(self.position, name="position")
        target = finite_point3(self.target, name="target")
        up = finite_point3(self.up, name="up")
        _reject_degenerate_basis(position, target, up)
        if self.projection not in ("perspective", "orthographic"):
            raise ViewError("projection must be 'perspective' or 'orthographic'")
        if not isfinite(self.fov_degrees) or self.fov_degrees <= 0.0 or self.fov_degrees >= 180.0:
            raise ViewError("fov_degrees must be between 0 and 180")
        if not isfinite(self.orthographic_scale) or self.orthographic_scale <= 0.0:
            raise ViewError("orthographic_scale must be positive")
        if not isfinite(self.near) or not isfinite(self.far) or self.near <= 0.0:
            raise ViewError("near and far clipping planes must be positive finite values")
        if self.far <= self.near:
            raise ViewError("far clipping plane must be greater than near")
        min_distance = _optional_positive(self.min_distance, "min_distance")
        max_distance = _optional_positive(self.max_distance, "max_distance")
        min_orthographic_scale = _optional_positive(
            self.min_orthographic_scale,
            "min_orthographic_scale",
        )
        max_orthographic_scale = _optional_positive(
            self.max_orthographic_scale,
            "max_orthographic_scale",
        )
        if (
            min_distance is not None
            and max_distance is not None
            and min_distance > max_distance
        ):
            raise ViewError("min_distance must be less than or equal to max_distance")
        if (
            min_orthographic_scale is not None
            and max_orthographic_scale is not None
            and min_orthographic_scale > max_orthographic_scale
        ):
            raise ViewError(
                "min_orthographic_scale must be less than or equal to max_orthographic_scale"
            )
        object.__setattr__(self, "position", position)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "up", up)
        object.__setattr__(self, "min_distance", min_distance)
        object.__setattr__(self, "max_distance", max_distance)
        object.__setattr__(self, "min_orthographic_scale", min_orthographic_scale)
        object.__setattr__(self, "max_orthographic_scale", max_orthographic_scale)

    @classmethod
    def look_at(
        cls,
        *,
        position: object,
        target: object,
        up: object = (0.0, 0.0, 1.0),
    ) -> Camera:
        """Create a camera from explicit position, target, and up vectors."""
        return cls(
            cast(Point3, position),
            cast(Point3, target),
            cast(Point3, up),
        )

    @classmethod
    def perspective(
        cls,
        *,
        position: object,
        target: object,
        up: object = (0.0, 0.0, 1.0),
        fov_degrees: float = 45.0,
        min_distance: float | None = None,
        max_distance: float | None = None,
    ) -> Camera:
        """Create a perspective camera."""
        return cls(
            cast(Point3, position),
            cast(Point3, target),
            cast(Point3, up),
            projection="perspective",
            fov_degrees=fov_degrees,
            min_distance=min_distance,
            max_distance=max_distance,
        )

    @classmethod
    def orthographic(
        cls,
        *,
        position: object,
        target: object,
        up: object = (0.0, 0.0, 1.0),
        scale: float = 1.0,
        min_scale: float | None = None,
        max_scale: float | None = None,
    ) -> Camera:
        """Create an orthographic camera."""
        return cls(
            cast(Point3, position),
            cast(Point3, target),
            cast(Point3, up),
            projection="orthographic",
            orthographic_scale=scale,
            min_orthographic_scale=min_scale,
            max_orthographic_scale=max_scale,
        )


def _optional_positive(value: float | None, name: str) -> float | None:
    if value is None:
        return None
    if not isfinite(value) or value <= 0.0:
        raise ViewError(f"{name} must be positive")
    return float(value)


__all__ = ["Camera", "Projection"]
