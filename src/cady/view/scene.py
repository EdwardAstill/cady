"""Scene graph values for backend-independent viewing."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any, cast

from cady.product.material import Metadata, metadata_items
from cady.view.camera import Camera
from cady.view.errors import ViewError
from cady.view.light import AmbientLight, DirectionalLight, Light
from cady.view.overlay import LocalAxesOverlay, ScaleBarOverlay, SceneOverlay
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
    """Immutable collection of objects, camera, lights, and overlays."""

    name: str = "scene"
    camera: Camera = field(
        default_factory=lambda: Camera.perspective(
            position=(1.8, -2.0, 1.2),
            target=(0.0, 0.0, 0.0),
            fov_degrees=45.0,
        )
    )
    lights: tuple[Light, ...] = field(
        default_factory=lambda: (
            AmbientLight(intensity=0.4),
            DirectionalLight(direction=(0.2, 0.45, 0.9), intensity=0.72),
        )
    )
    overlays: tuple[SceneOverlay, ...] = field(
        default_factory=lambda: (ScaleBarOverlay(), LocalAxesOverlay())
    )
    objects: tuple[SceneObject, ...] = field(default_factory=tuple)
    units: str = "m"
    metadata: Metadata = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.name:
            raise ViewError("scene name cannot be empty")
        camera = cast(object, self.camera)
        if not isinstance(camera, Camera):
            raise ViewError("scene camera must be a Camera")
        object.__setattr__(self, "objects", tuple(self.objects))
        object.__setattr__(self, "lights", tuple(self.lights))
        object.__setattr__(self, "overlays", tuple(self.overlays))
        object.__setattr__(self, "metadata", metadata_items(self.metadata))
        for light in cast(tuple[object, ...], self.lights):
            if not isinstance(light, Light):
                raise ViewError("scene lights must be Light values")
        for overlay in cast(tuple[object, ...], self.overlays):
            if not isinstance(overlay, (ScaleBarOverlay, LocalAxesOverlay)):
                raise ViewError("scene overlays must be SceneOverlay values")

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
        return replace(self, objects=(*self.objects, obj))

    def with_camera(self, camera: object, *, name: str = "camera", active: bool = True) -> Scene:
        """Return a copy with a replacement camera.

        The name and active arguments are accepted for compatibility with the
        older named-camera scene API.
        """
        if not isinstance(camera, Camera):
            raise ViewError("camera must be a Camera")
        return replace(self, camera=camera)

    def with_light(self, light: object) -> Scene:
        """Return a copy with an additional light."""
        if not isinstance(light, Light):
            raise ViewError("light must be a Light")
        return replace(self, lights=(*self.lights, light))

    def with_overlay(self, overlay: object) -> Scene:
        """Return a copy with an additional overlay."""
        if not isinstance(overlay, (ScaleBarOverlay, LocalAxesOverlay)):
            raise ViewError("overlay must be a SceneOverlay value")
        return replace(self, overlays=(*self.overlays, overlay))

    def view(self, *, tolerance: float = 1e-3, title: str | None = None) -> None:
        """Open this scene in the interactive viewer."""
        from cady import view as view_module

        view_scene = cast(Callable[..., None], view_module.view_scene)
        view_scene(self, tolerance=tolerance, title=title)
        return None

    def with_metadata(self, **metadata: Any) -> Scene:
        """Return a copy with merged scene metadata."""
        return replace(self, metadata=metadata_items(dict(self.metadata) | metadata))


__all__ = ["Scene", "SceneObject"]
