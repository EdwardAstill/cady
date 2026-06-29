"""Helpers for opening a quick fitted view of a single target."""

from __future__ import annotations

from collections.abc import Callable, Sized
from math import sqrt
from typing import Literal, cast

from cady.document import Document
from cady.geometry import Mesh3
from cady.utils import positive_tolerance
from cady.view._coordinates import finite_point3
from cady.view.camera import Camera
from cady.view.errors import ViewError
from cady.view.light import DirectionalLight, Light
from cady.view.scene import Scene
from cady.view.style import DisplayStyle, RenderMode

Projection = Literal["orthographic", "perspective"]

DEFAULT_VIEW_COLOR = (0.62, 0.68, 0.72)
DEFAULT_WIRE_COLOR = (0.05, 0.23, 0.55)
DEFAULT_VIEW_LIGHT = DirectionalLight(direction=(-1.0, -1.0, -2.0), intensity=1.4)
DEFAULT_VIEW_ASPECT = 900.0 / 700.0
DEFAULT_FOV_DEGREES = 35.0
FIT_PADDING = 1.18


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
        Scene(scene_name)
        .add(target, name=name, pose=pose, style=resolved_style)
        .with_camera(resolved_camera, name="view")
        .with_light(light or DEFAULT_VIEW_LIGHT)
    )

    # Import through the public view module so GUI backends stay lazy.
    from cady import view as view_module

    view_scene = cast(Callable[..., None], view_module.view_scene)
    view_scene(scene, tolerance=tolerance, title=title)
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
    if callable(getattr(target, "bounds", None)):
        return target
    # Delegate mesh coercion here so documents, mesh values, and meshable domain
    # objects all share the same compatibility rules and error messages.
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


__all__ = ["open_target_view"]
