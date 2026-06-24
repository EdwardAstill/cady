from __future__ import annotations

from cady.view import Scene
from cady.visualisation.vispy_viewer import (
    PreparedScene,
    SceneLine,
    SceneMesh,
    prepare_scene,
    view_lines,
    view_mesh,
    view_meshes,
    view_scene,
    view_target,
)


def scene_from_target(target: object, *, name: str = "scene") -> Scene:
    return Scene.from_target(target, name=name)


__all__ = [
    "PreparedScene",
    "SceneLine",
    "SceneMesh",
    "prepare_scene",
    "scene_from_target",
    "view_lines",
    "view_mesh",
    "view_meshes",
    "view_scene",
    "view_target",
]
