"""Backend-agnostic view API with lazily imported viewer helpers."""

from typing import TYPE_CHECKING

from cady.view.camera import Camera
from cady.view.errors import ViewError
from cady.view.light import AmbientLight, DirectionalLight, Light, PointLight
from cady.view.overlay import ScaleBarOverlay, SceneOverlay
from cady.view.scene import Scene, SceneObject
from cady.view.style import DisplayStyle

if TYPE_CHECKING:
    from cady.view.preparation import (
        PreparedScene,
        SceneLine,
        SceneMesh,
        prepare_scene,
    )
    from cady.view.vispy_viewer import (
        view_lines,
        view_mesh,
        view_meshes,
        view_scene,
        view_target,
    )

_PREPARATION_EXPORTS = frozenset(
    {
        "PreparedScene",
        "SceneLine",
        "SceneMesh",
        "prepare_scene",
    }
)
_VIEWER_EXPORTS = frozenset(
    {
        "view_lines",
        "view_mesh",
        "view_meshes",
        "view_scene",
        "view_target",
    }
)


def scene_from_target(target: object, *, name: str = "scene") -> Scene:
    """Build a single-object scene from any supported view target."""
    return Scene.from_target(target, name=name)


def __getattr__(name: str) -> object:
    if name in _PREPARATION_EXPORTS:
        # Scene preparation is backend-independent and does not open GUI paths.
        from cady.view import preparation

        return getattr(preparation, name)
    if name in _VIEWER_EXPORTS:
        # Defer viewer backend imports until a GUI-facing helper is requested.
        from cady.view import vispy_viewer

        return getattr(vispy_viewer, name)
    raise AttributeError(f"module 'cady.view' has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted((*globals(), *_PREPARATION_EXPORTS, *_VIEWER_EXPORTS))


__all__ = [
    "AmbientLight",
    "Camera",
    "DirectionalLight",
    "DisplayStyle",
    "Light",
    "PointLight",
    "PreparedScene",
    "ScaleBarOverlay",
    "Scene",
    "SceneLine",
    "SceneMesh",
    "SceneObject",
    "SceneOverlay",
    "ViewError",
    "prepare_scene",
    "scene_from_target",
    "view_lines",
    "view_mesh",
    "view_meshes",
    "view_scene",
    "view_target",
]
