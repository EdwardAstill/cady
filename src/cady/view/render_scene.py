"""Backend-independent conversion of scenes into renderable arrays."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypeAlias

import numpy as np

from cady.document import Document
from cady.geometry import Mesh3, PointCloud3, Wireframe3
from cady.operations.transforms import Transform3
from cady.product import Assembly, Part
from cady.utils import positive_tolerance
from cady.view.camera import Camera
from cady.view.errors import ViewError
from cady.view.light import AmbientLight, DirectionalLight
from cady.view.overlay import SceneOverlay
from cady.view.scene import Scene
from cady.view.style import DisplayStyle

LineVertices: TypeAlias = Sequence[Sequence[float]] | np.ndarray

_DEFAULT_MESH_COLOR = (0.45, 0.58, 0.72)
DEFAULT_CAMERA = Camera.perspective(
    position=(1.8, -2.0, 1.2),
    target=(0.0, 0.0, 0.0),
    fov_degrees=45.0,
)


@dataclass(frozen=True, slots=True)
class SceneMesh:
    """Mesh payload prepared for the viewer backend."""

    name: str
    vertices: np.ndarray
    faces: np.ndarray
    edges: np.ndarray
    color: tuple[float, float, float]
    render_mode: str
    point_size: float = 4.0


@dataclass(frozen=True, slots=True)
class SceneLine:
    """Polyline payload prepared for the viewer backend."""

    name: str
    vertices: np.ndarray
    indices: np.ndarray
    color: tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class RenderScene:
    """Scene data converted into arrays and lighting values for rendering."""

    name: str
    meshes: tuple[SceneMesh, ...]
    lines: tuple[SceneLine, ...]
    camera: Camera
    ambient_light: tuple[float, float, float]
    diffuse_light: tuple[float, float, float]
    light_direction: tuple[float, float, float]
    overlays: tuple[SceneOverlay, ...] = ()


def prepare_scene(scene: Scene, *, tolerance: float = 1e-3) -> RenderScene:
    """Convert scene objects into mesh and line buffers for rendering."""
    meshes: list[SceneMesh] = []
    lines: list[SceneLine] = []
    for scene_object in scene.objects:
        style = scene_object.style or DisplayStyle()
        if not style.visible:
            continue
        target = scene_object.target
        transform = (
            transform_from_pose(scene_object.pose) if scene_object.pose is not None else None
        )
        point_cloud = _point_cloud_from_target(target)
        if point_cloud is not None:
            if transform is not None:
                point_cloud = point_cloud.transformed(transform)
            if len(point_cloud.vertices) > 0:
                meshes.append(
                    SceneMesh(
                        scene_object.object_name,
                        np.asarray(point_cloud.vertices, dtype=np.float32),
                        np.empty((0, 3), dtype=np.uint32),
                        np.empty((0, 2), dtype=np.uint32),
                        _style_color(target, style),
                        "points",
                        style.point_size,
                    )
                )
            continue

        line = _line_from_target(target, transform=transform)
        if line is not None:
            vertices, indices = line
            if len(indices) > 0:
                lines.append(
                    SceneLine(
                        scene_object.object_name,
                        vertices,
                        indices,
                        _style_color(target, style),
                    )
                )
            continue

        mesh = _mesh_from_target(target, tolerance=tolerance)
        if transform is not None:
            mesh = mesh.transformed(transform)
        if len(mesh.vertices) > 0:
            vertices, faces, edges = mesh.to_array(tolerance=tolerance)
            meshes.append(
                SceneMesh(
                    scene_object.object_name,
                    vertices.astype(np.float32, copy=False),
                    faces.astype(np.uint32, copy=False),
                    edges.astype(np.uint32, copy=False),
                    _style_color(target, style),
                    style.render_mode,
                    style.point_size,
                )
            )

    if not meshes and not lines:
        raise ValueError("cannot visualise an empty scene")

    ambient, diffuse, light_direction = _lighting(scene)
    return RenderScene(
        scene.name,
        tuple(meshes),
        tuple(lines),
        scene.camera,
        ambient,
        diffuse,
        light_direction,
        scene.overlays,
    )


def _polyline_indices(vertex_count: int) -> np.ndarray:
    if vertex_count < 2:
        return np.empty((0, 2), dtype=np.uint32)
    starts = np.arange(0, vertex_count - 1, dtype=np.uint32)
    ends = np.arange(1, vertex_count, dtype=np.uint32)
    return np.column_stack((starts, ends)).astype(np.uint32, copy=False)


def prepare_polyline(vertices: LineVertices) -> tuple[np.ndarray, np.ndarray]:
    try:
        rows = [_polyline_point_row(point) for point in vertices]
    except TypeError as exc:
        raise ValueError("line vertices must be an (N, 3) array") from exc
    points = np.asarray(rows, dtype=np.float32)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError("line vertices must be an (N, 3) array")
    return points, _polyline_indices(len(points))


def _polyline_point_row(point: object) -> object:
    as_tuple = getattr(point, "tuple", None)
    if callable(as_tuple):
        return as_tuple()
    return point


def _mesh_from_target(target: object, *, tolerance: float) -> Mesh3:
    if isinstance(target, Wireframe3):
        return Mesh3(target.vertices, (), target.edges)
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
    raise ViewError("scene target must be Mesh3, Wireframe3, or expose to_mesh(tolerance=...)")


def _point_cloud_from_target(target: object) -> PointCloud3 | None:
    if isinstance(target, PointCloud3):
        return target
    return None


def _line_from_target(
    target: object,
    *,
    transform: Transform3 | None,
) -> tuple[np.ndarray, np.ndarray] | None:
    try:
        vertices, indices = prepare_polyline(target)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if transform is not None:
        vertices = transform.apply_points(vertices).astype(np.float32, copy=False)
    return vertices, indices


def transform_from_pose(pose: object) -> Transform3:
    try:
        return Transform3.coerce(pose)
    except TypeError as exc:
        raise TypeError(
            "scene object pose must be Transform3-like or a 3D translation"
        ) from exc


def _style_color(target: object, style: DisplayStyle) -> tuple[float, float, float]:
    if style.color is not None:
        return style.color
    if (
        isinstance(target, Part)
        and target.material is not None
        and target.material.color is not None
    ):
        return target.material.color
    if isinstance(target, Assembly):
        return _DEFAULT_MESH_COLOR
    return _DEFAULT_MESH_COLOR


def _lighting(
    scene: Scene,
) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    ambient = np.array((0.28, 0.28, 0.28), dtype=np.float32)
    diffuse = np.array((0.72, 0.72, 0.72), dtype=np.float32)
    direction = np.array((0.2, 0.45, 0.9), dtype=np.float32)
    ambient_seen = False
    directional_seen = False

    for light in scene.lights:
        color = np.array(light.color, dtype=np.float32)
        if isinstance(light, AmbientLight):
            ambient = color * float(light.intensity)
            ambient_seen = True
        elif isinstance(light, DirectionalLight) and not directional_seen:
            direction = np.array(light.direction, dtype=np.float32)
            diffuse = color * float(light.intensity)
            directional_seen = True

    if not ambient_seen:
        ambient = np.array((0.28, 0.28, 0.28), dtype=np.float32)
    if not directional_seen:
        diffuse = np.array((0.72, 0.72, 0.72), dtype=np.float32)

    return (
        _array3_tuple(np.clip(ambient, 0.0, 1.0)),
        _array3_tuple(np.clip(diffuse, 0.0, 1.0)),
        _array3_tuple(direction),
    )


def _array3_tuple(values: np.ndarray) -> tuple[float, float, float]:
    return (float(values[0]), float(values[1]), float(values[2]))


__all__ = [
    "DEFAULT_CAMERA",
    "LineVertices",
    "RenderScene",
    "SceneLine",
    "SceneMesh",
    "prepare_polyline",
    "prepare_scene",
    "transform_from_pose",
]
