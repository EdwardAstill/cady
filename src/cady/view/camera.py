"""Camera definitions and validation for backend-independent scenes."""

from __future__ import annotations

from dataclasses import dataclass
from math import acos, degrees, isfinite
from typing import Literal, cast

from cady.operations.coordinates import dot3, length3, sub3
from cady.view._coordinates import Point3, finite_point3
from cady.view.errors import ViewError

Projection = Literal["perspective", "orthographic"]


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
        object.__setattr__(self, "position", position)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "up", up)

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
    ) -> Camera:
        """Create a perspective camera."""
        return cls(
            cast(Point3, position),
            cast(Point3, target),
            cast(Point3, up),
            projection="perspective",
            fov_degrees=fov_degrees,
        )

    @classmethod
    def orthographic(
        cls,
        *,
        position: object,
        target: object,
        up: object = (0.0, 0.0, 1.0),
        scale: float = 1.0,
    ) -> Camera:
        """Create an orthographic camera."""
        return cls(
            cast(Point3, position),
            cast(Point3, target),
            cast(Point3, up),
            projection="orthographic",
            orthographic_scale=scale,
        )


__all__ = ["Camera", "Projection"]
