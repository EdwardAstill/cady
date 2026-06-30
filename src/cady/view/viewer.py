"""Interactive 3D scene viewer using VisPy.

VisPy is imported lazily so importing :mod:`cady.view` does not require GUI
packages unless a viewer is actually launched.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Iterable, Sequence, Sized
from math import isfinite, sqrt
from typing import Any, Literal, cast

import numpy as np

from cady.document import Document
from cady.geometry import Mesh3
from cady.utils import positive_tolerance
from cady.view.camera import Camera
from cady.view.errors import ViewError
from cady.view.light import AmbientLight, DirectionalLight, Light
from cady.view.scene import (
    DEFAULT_CAMERA,
    LineVertices,
    RenderScene,
    Scene,
    SceneLine,
    SceneMesh,
    prepare_polyline,
    prepare_scene,
)
from cady.view.style import DisplayStyle, RenderMode
from cady.view.vispy.canvas import (
    _make_vispy_canvas,
    _require_vispy,
)

Projection = Literal["orthographic", "perspective"]
_DEFAULT_LINE_COLOR = (0.05, 0.23, 0.55)
DEFAULT_VIEW_COLOR = (0.62, 0.68, 0.72)
DEFAULT_WIRE_COLOR = (0.05, 0.23, 0.55)
DEFAULT_VIEW_LIGHT = DirectionalLight(direction=(-1.0, -1.0, -2.0), intensity=1.4)
DEFAULT_VIEW_ASPECT = 900.0 / 700.0
DEFAULT_FOV_DEGREES = 35.0
FIT_PADDING = 1.18


def finite_point3(value: object, *, name: str = "point") -> tuple[float, float, float]:
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


def view_scene(scene: Scene, *, tolerance: float = 1e-3, title: str | None = None) -> object:
    """Open an interactive window for a prepared scene."""
    _require_vispy()
    app = cast(Any, importlib.import_module("vispy.app"))
    _make_vispy_canvas(prepare_scene(scene, tolerance=tolerance), title=title)
    app.run()
    return None


def view_mesh(mesh: object, *, tolerance: float = 1e-3, title: str | None = None) -> object:
    """Open an interactive window for one mesh-like target."""
    resolved_title = title or "cady 3D mesh"
    scene = Scene.from_target(mesh, name=resolved_title)
    return view_scene(scene, tolerance=tolerance, title=resolved_title)


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


def open_target_view(
    target: object,
    *,
    name: str | None = None,
    title: str | None = None,
    camera: Camera | None = None,
    style: DisplayStyle | None = None,
    light: Light | None = None,
    color: tuple[float, float, float] | None = None,
    render_mode: RenderMode | None = None,
    projection: Projection = "orthographic",
    center: bool = True,
    tolerance: float = 1e-3,
) -> None:
    """Open an interactive view for one target with a fitted camera."""
    if tolerance <= 0.0:
        raise ViewError("tolerance must be positive")

    bounds, wire_only = _target_bounds_and_wire_mode(target, tolerance=tolerance)
    # Centering applies only as a scene pose, leaving the original target value
    # unchanged while giving the default camera a stable origin to orbit.
    pose = _origin_pose(bounds) if center else None
    camera_bounds = _centred_bounds(bounds) if center else bounds
    resolved_style = style or _default_style(
        color=color,
        render_mode=render_mode,
        wire_only=wire_only,
    )
    resolved_camera = camera or _fit_camera(camera_bounds, projection=projection)
    scene_name = title or name or _target_name(target)
    scene = (
        Scene(
            scene_name,
            camera=resolved_camera,
            lights=(AmbientLight(intensity=0.4), light or DEFAULT_VIEW_LIGHT),
        )
        .add(target, name=name, pose=pose, style=resolved_style)
    )

    # Import through the public view module so tests can patch the public helper.
    from cady import view as view_module

    public_view_scene = cast(Callable[..., None], view_module.view_scene)
    public_view_scene(scene, tolerance=tolerance, title=title)
    return None


def _default_style(
    *,
    color: tuple[float, float, float] | None,
    render_mode: RenderMode | None,
    wire_only: bool,
) -> DisplayStyle:
    """Choose a default style for shaded and wire-only targets."""
    resolved_mode = render_mode or ("wireframe" if wire_only else "shaded")
    resolved_color = color or (
        DEFAULT_WIRE_COLOR if resolved_mode == "wireframe" else DEFAULT_VIEW_COLOR
    )
    return DisplayStyle(color=resolved_color, render_mode=resolved_mode)


def _target_bounds_and_wire_mode(
    target: object,
    *,
    tolerance: float,
) -> tuple[tuple[tuple[float, float, float], tuple[float, float, float]], bool]:
    geometry = _mesh_like(target, tolerance=tolerance)
    bounds_method = getattr(geometry, "bounds", None)
    if not callable(bounds_method):
        raise ViewError("view target must expose bounds() or to_mesh(tolerance=...)")
    lower, upper = cast(tuple[object, object], bounds_method())
    return (
        (
            finite_point3(lower, name="bounds lower"),
            finite_point3(upper, name="bounds upper"),
        ),
        _is_wire_only(geometry),
    )


def _mesh_like(target: object, *, tolerance: float) -> object:
    # Prefer a target's own bounds when available so viewer launch does not
    # force an avoidable mesh conversion.
    if callable(getattr(target, "bounds", None)):
        return target
    if isinstance(target, (Document, Mesh3)) or callable(getattr(target, "to_mesh", None)):
        return _mesh_from_target(target, tolerance=tolerance)
    to_array = getattr(target, "to_array", None)
    if callable(to_array):
        return to_array(tolerance=tolerance)
    return target


def _mesh_from_target(target: object, *, tolerance: float) -> Mesh3:
    try:
        positive_tolerance(tolerance)
    except ValueError as exc:
        raise ViewError(str(exc)) from exc

    if isinstance(target, Mesh3):
        return target

    if isinstance(target, Document):
        meshes = [
            _mesh_from_target(item.value, tolerance=tolerance)
            for item in (*target.parts, *target.assemblies)
        ]
        if not meshes:
            raise ViewError("document contains no meshable parts or assemblies")
        return Mesh3.merged(meshes)

    to_mesh = getattr(target, "to_mesh", None)
    if callable(to_mesh):
        mesh = to_mesh(tolerance=tolerance)
        if isinstance(mesh, Mesh3):
            return mesh
        raise ViewError("to_mesh() must return Mesh3")

    raise ViewError("view target must expose bounds() or to_mesh(tolerance=...)")


def _is_wire_only(target: object) -> bool:
    faces = getattr(target, "faces", None)
    edges = getattr(target, "edges", None)
    if not isinstance(faces, Sized) or not isinstance(edges, Sized):
        return False
    return len(faces) == 0 and len(edges) > 0


def _fit_camera(
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]],
    *,
    projection: Projection,
) -> Camera:
    """Fit a simple front-right-above camera to the given bounds."""
    lower, upper = bounds
    centre = (
        (lower[0] + upper[0]) / 2.0,
        (lower[1] + upper[1]) / 2.0,
        (lower[2] + upper[2]) / 2.0,
    )
    span = (upper[0] - lower[0], upper[1] - lower[1], upper[2] - lower[2])
    radius = max(sqrt(span[0] ** 2 + span[1] ** 2 + span[2] ** 2) / 2.0, 1.0)
    distance = radius * 3.0
    position = (
        centre[0] + distance,
        centre[1] - distance,
        centre[2] + distance * 0.65,
    )
    if projection == "perspective":
        return Camera.perspective(
            position=position,
            target=centre,
            fov_degrees=DEFAULT_FOV_DEGREES,
        )
    if projection != "orthographic":
        raise ViewError("projection must be 'orthographic' or 'perspective'")
    scale = max(span[2], span[0] / DEFAULT_VIEW_ASPECT, span[1], 1.0) * FIT_PADDING
    return Camera.orthographic(position=position, target=centre, scale=scale)


def _target_name(target: object) -> str:
    name = getattr(target, "name", None)
    if isinstance(name, str) and name:
        return name
    return type(target).__name__


def _origin_pose(
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]],
) -> object:
    from cady.operations import Transform3

    lower, upper = bounds
    centre = _centre(lower, upper)
    return Transform3().translate(-centre[0], -centre[1], -centre[2])


def _centred_bounds(
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]],
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    lower, upper = bounds
    centre = _centre(lower, upper)
    return (
        (lower[0] - centre[0], lower[1] - centre[1], lower[2] - centre[2]),
        (upper[0] - centre[0], upper[1] - centre[1], upper[2] - centre[2]),
    )


def _centre(
    lower: tuple[float, float, float],
    upper: tuple[float, float, float],
) -> tuple[float, float, float]:
    return (
        (lower[0] + upper[0]) / 2.0,
        (lower[1] + upper[1]) / 2.0,
        (lower[2] + upper[2]) / 2.0,
    )


__all__ = [
    "Projection",
    "RenderScene",
    "SceneLine",
    "SceneMesh",
    "open_target_view",
    "prepare_scene",
    "view_lines",
    "view_mesh",
    "view_meshes",
    "view_scene",
]
