"""Interactive 3D scene viewer using VisPy.

VisPy is imported lazily so importing :mod:`cady.view` does not require GUI
packages unless a viewer is actually launched.
"""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from typing import Any, cast

import numpy as np

from cady.view.draw_batches import mesh_edge_color
from cady.view.interaction import (
    axis_toggle_key_pressed,
    camera_orientation,
    number_key_name,
    projection_clip_planes,
    view_relative_orthographic_axis_length,
    zoomed_orthographic_scale,
)
from cady.view.mesh_buffers import orientation_edges, shaded_face_buffers
from cady.view.overlay_renderers import (
    scale_bar_for_camera,
    scale_bar_for_visible_height,
    scale_bar_overlay,
)
from cady.view.render_scene import (
    DEFAULT_CAMERA,
    LineVertices,
    RenderScene,
    SceneLine,
    SceneMesh,
    prepare_polyline,
    prepare_scene,
    transform_from_pose,
)
from cady.view.scene import Scene
from cady.view.vispy_canvas import (
    _make_vispy_canvas,
    _require_vispy,
)

_transform_from_pose = transform_from_pose
_mesh_edge_color = mesh_edge_color
_camera_orientation = camera_orientation
_view_relative_orthographic_axis_length = view_relative_orthographic_axis_length
_zoomed_orthographic_scale = zoomed_orthographic_scale
_orientation_edges = orientation_edges
_shaded_face_buffers = shaded_face_buffers
_scale_bar_for_camera = scale_bar_for_camera
_scale_bar_for_visible_height = scale_bar_for_visible_height
_scale_bar_overlay = scale_bar_overlay
_axis_toggle_key_pressed = axis_toggle_key_pressed
_number_key_name = number_key_name
_projection_clip_planes = projection_clip_planes

_DEFAULT_LINE_COLOR = (0.05, 0.23, 0.55)


def view_scene(scene: Scene, *, tolerance: float = 1e-3, title: str | None = None) -> object:
    """Open an interactive window for a prepared scene."""
    _require_vispy()
    app = cast(Any, importlib.import_module("vispy.app"))
    _make_vispy_canvas(prepare_scene(scene, tolerance=tolerance), title=title)
    app.run()
    return None


def view_target(
    target: object,
    *,
    tolerance: float = 1e-3,
    title: str | None = None,
) -> object:
    """Open an interactive window for a single target."""
    scene = Scene.from_target(
        target,
        name=title or "cady 3D viewer",
    )
    return view_scene(scene, tolerance=tolerance, title=title)


def view_mesh(mesh: object, *, tolerance: float = 1e-3, title: str | None = None) -> object:
    """Open an interactive window for one mesh-like target."""
    return view_target(mesh, tolerance=tolerance, title=title or "cady 3D mesh")


def view_meshes(
    meshes: Sequence[object],
    *,
    tolerance: float = 1e-3,
    title: str = "cady 3D meshes",
) -> object:
    """Open an interactive window for multiple mesh-like targets."""
    scene = Scene(name=title)
    for index, mesh in enumerate(meshes):
        scene = scene.add(mesh, name=f"mesh_{index + 1}")
    return view_scene(scene, tolerance=tolerance, title=title)


def view_lines(
    lines: Sequence[LineVertices],
    *,
    title: str = "cady 3D wire viewer",
) -> object:
    """Open an interactive window for one or more polylines."""
    _require_vispy()
    vertices: list[np.ndarray] = []
    indices: list[np.ndarray] = []
    segment_count = 0
    for line in lines:
        line_vertices, line_indices = prepare_polyline(line)
        vertices.append(line_vertices)
        indices.append(line_indices)
        segment_count += len(line_indices)

    if segment_count == 0:
        raise ValueError("view_lines requires at least one line segment")

    scene_lines = tuple(
        SceneLine(
            f"line_{index + 1}",
            vertices[index],
            indices[index],
            _DEFAULT_LINE_COLOR,
        )
        for index in range(len(vertices))
    )
    prepared = RenderScene(
        title,
        (),
        scene_lines,
        DEFAULT_CAMERA,
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
        (0.0, 0.0, -1.0),
    )

    app = cast(Any, importlib.import_module("vispy.app"))
    _make_vispy_canvas(prepared, title=title)
    app.run()
    return None


__all__ = [
    "RenderScene",
    "SceneLine",
    "SceneMesh",
    "prepare_scene",
    "view_lines",
    "view_mesh",
    "view_meshes",
    "view_scene",
    "view_target",
]
