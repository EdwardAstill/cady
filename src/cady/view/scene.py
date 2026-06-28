"""Scene graph values for backend-independent viewing."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from cady.product.material import Metadata, metadata_items
from cady.view.camera import Camera
from cady.view.errors import ViewError
from cady.view.light import AmbientLight, Light
from cady.view.style import DisplayStyle


@dataclass(frozen=True, slots=True)
class SceneObject:
    """Reference to a target object together with pose and style overrides."""

    target: object
    name: str | None = None
    pose: object | None = None
    style: DisplayStyle | None = None
    metadata: Metadata = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.target is None:
            raise ViewError("scene object target cannot be None")
        if self.name is not None and not self.name:
            raise ViewError("scene object name cannot be empty")
        object.__setattr__(self, "metadata", metadata_items(self.metadata))

    @property
    def object_name(self) -> str:
        """Return the explicit name, target name, or target type name."""
        if self.name is not None:
            return self.name
        target_name = getattr(self.target, "name", None)
        if isinstance(target_name, str) and target_name:
            return target_name
        return type(self.target).__name__


@dataclass(frozen=True, slots=True)
class Scene:
    """Immutable collection of objects, cameras, and lights."""

    name: str = "scene"
    objects: tuple[SceneObject, ...] = field(default_factory=tuple)
    cameras: tuple[tuple[str, Camera], ...] = field(default_factory=tuple)
    lights: tuple[Light, ...] = field(default_factory=lambda: (AmbientLight(intensity=0.4),))
    active_camera: str | None = None
    units: str = "m"
    metadata: Metadata = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.name:
            raise ViewError("scene name cannot be empty")
        object.__setattr__(self, "objects", tuple(self.objects))
        object.__setattr__(self, "cameras", tuple(self.cameras))
        object.__setattr__(self, "lights", tuple(self.lights))
        object.__setattr__(self, "metadata", metadata_items(self.metadata))
        camera_names = [name for name, _camera in self.cameras]
        if len(camera_names) != len(set(camera_names)):
            raise ViewError("duplicate camera names are not allowed")
        if self.active_camera is not None and self.active_camera not in camera_names:
            raise ViewError("active_camera must reference a camera in the scene")

    @classmethod
    def from_target(cls, target: object, *, name: str = "scene") -> Scene:
        """Create a scene containing a single target."""
        return cls(name=name).add(target)

    @classmethod
    def from_part(cls, part: object, *, name: str = "scene") -> Scene:
        """Create a single-part scene."""
        return cls.from_target(part, name=name)

    @classmethod
    def from_assembly(cls, assembly: object, *, name: str = "scene") -> Scene:
        """Create a single-assembly scene."""
        return cls.from_target(assembly, name=name)

    def add(
        self,
        target: object,
        *,
        name: str | None = None,
        pose: object | None = None,
        style: DisplayStyle | None = None,
        metadata: Mapping[str, Any] | Metadata | None = None,
    ) -> Scene:
        """Return a copy with one more target wrapped as a scene object."""
        return self.add_object(
            SceneObject(
                target,
                name=name,
                pose=pose,
                style=style,
                metadata=metadata_items(metadata),
            )
        )

    def add_object(self, obj: object) -> Scene:
        """Return a copy with an existing scene object appended."""
        if not isinstance(obj, SceneObject):
            raise ViewError("scene objects must be SceneObject values")
        return Scene(
            name=self.name,
            objects=(*self.objects, obj),
            cameras=self.cameras,
            lights=self.lights,
            active_camera=self.active_camera,
            units=self.units,
            metadata=self.metadata,
        )

    def with_camera(self, camera: object, *, name: str = "camera", active: bool = True) -> Scene:
        """Return a copy with an additional named camera."""
        if not isinstance(camera, Camera):
            raise ViewError("camera must be a Camera")
        if not name:
            raise ViewError("camera name cannot be empty")
        if any(existing == name for existing, _camera in self.cameras):
            raise ViewError(f"duplicate camera name: {name}")
        return Scene(
            name=self.name,
            objects=self.objects,
            cameras=(*self.cameras, (name, camera)),
            lights=self.lights,
            active_camera=name if active else self.active_camera,
            units=self.units,
            metadata=self.metadata,
        )

    def with_light(self, light: object) -> Scene:
        """Return a copy with an additional light."""
        if not isinstance(light, Light):
            raise ViewError("light must be a Light")
        return Scene(
            name=self.name,
            objects=self.objects,
            cameras=self.cameras,
            lights=(*self.lights, light),
            active_camera=self.active_camera,
            units=self.units,
            metadata=self.metadata,
        )

    def with_metadata(self, **metadata: Any) -> Scene:
        """Return a copy with merged scene metadata."""
        return Scene(
            name=self.name,
            objects=self.objects,
            cameras=self.cameras,
            lights=self.lights,
            active_camera=self.active_camera,
            units=self.units,
            metadata=metadata_items(dict(self.metadata) | metadata),
        )


__all__ = ["Scene", "SceneObject"]
