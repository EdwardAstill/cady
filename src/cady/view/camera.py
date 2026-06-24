from __future__ import annotations

from dataclasses import dataclass
from math import acos, degrees, isfinite, sqrt
from typing import Literal

from cady.view.errors import ViewError

Projection = Literal["perspective", "orthographic"]
Vec3Like = tuple[float, float, float]


def vec3(value: object, *, name: str) -> Vec3Like:
    try:
        raw = tuple(float(component) for component in value)  # type: ignore[reportUnknownVariableType]
    except TypeError as exc:
        raise ViewError(f"{name} must be a finite 3D vector") from exc
    if len(raw) != 3 or any(not isfinite(component) for component in raw):
        raise ViewError(f"{name} must be a finite 3D vector")
    return raw


def _sub(a: Vec3Like, b: Vec3Like) -> Vec3Like:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Vec3Like, b: Vec3Like) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _length(a: Vec3Like) -> float:
    return sqrt(_dot(a, a))


def _reject_degenerate_basis(position: Vec3Like, target: Vec3Like, up: Vec3Like) -> None:
    view = _sub(target, position)
    view_length = _length(view)
    up_length = _length(up)
    if view_length == 0.0:
        raise ViewError("camera position and target must be different")
    if up_length == 0.0:
        raise ViewError("camera up vector must be non-zero")
    cosine = abs(_dot(view, up) / (view_length * up_length))
    if degrees(acos(min(1.0, cosine))) < 1e-6:
        raise ViewError("camera up vector must not be parallel to the view direction")


@dataclass(frozen=True, slots=True)
class Camera:
    position: Vec3Like
    target: Vec3Like
    up: Vec3Like = (0.0, 0.0, 1.0)
    projection: Projection = "perspective"
    fov_degrees: float = 45.0
    orthographic_scale: float = 1.0
    near: float = 1e-3
    far: float = 1e6

    def __post_init__(self) -> None:
        position = vec3(self.position, name="position")
        target = vec3(self.target, name="target")
        up = vec3(self.up, name="up")
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
        return cls(
            vec3(position, name="position"),
            vec3(target, name="target"),
            vec3(up, name="up"),
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
        return cls(
            vec3(position, name="position"),
            vec3(target, name="target"),
            vec3(up, name="up"),
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
        return cls(
            vec3(position, name="position"),
            vec3(target, name="target"),
            vec3(up, name="up"),
            projection="orthographic",
            orthographic_scale=scale,
        )


__all__ = ["Camera", "Projection", "Vec3Like", "vec3"]
