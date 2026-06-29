"""Interactive 3D scene viewer using VisPy.

VisPy is imported lazily so importing :mod:`cady.view` does not require GUI
packages unless a viewer is actually launched.
"""

from __future__ import annotations

import importlib
import importlib.util
from collections.abc import Sequence
from dataclasses import dataclass
from math import cos, floor, log10, radians, tan
from typing import Any, cast

import numpy as np

from cady.view.camera import Camera
from cady.view.mesh_buffers import orientation_edges as _orientation_edges
from cady.view.mesh_buffers import shaded_face_buffers as _shaded_face_buffers
from cady.view.preparation import (
    DEFAULT_CAMERA,
    LineVertices,
    PreparedScene,
    SceneLine,
    SceneMesh,
    prepare_polyline,
    prepare_scene,
    transform_from_pose,
)
from cady.view.scene import Scene

_transform_from_pose = transform_from_pose

_VERT_SHADER = """
uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;
uniform float u_point_size;
attribute vec3 a_position;
attribute vec3 a_normal;
attribute vec3 a_color;
varying vec3 v_color;
varying vec3 v_normal;
void main() {
    v_color = a_color;
    v_normal = normalize((u_model * vec4(a_normal, 0.0)).xyz);
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
    gl_PointSize = u_point_size;
}
"""

_FRAG_SHADER = """
uniform vec3 u_light_direction;
uniform vec3 u_ambient_light;
uniform vec3 u_diffuse_light;
uniform float u_lighting;
varying vec3 v_color;
varying vec3 v_normal;
void main() {
    vec3 normal = normalize(v_normal);
    float diffuse = abs(dot(normal, normalize(u_light_direction)));
    vec3 lit = v_color * clamp(u_ambient_light + diffuse * u_diffuse_light, 0.0, 1.0);
    gl_FragColor = vec4(mix(v_color, lit, u_lighting), 1.0);
}
"""

_OVERLAY_VERT_SHADER = """
attribute vec2 a_position;
void main() {
    gl_Position = vec4(a_position, 0.0, 1.0);
}
"""

_OVERLAY_FRAG_SHADER = """
uniform vec3 u_color;
void main() {
    gl_FragColor = vec4(u_color, 1.0);
}
"""

_HAS_VISPY = importlib.util.find_spec("vispy") is not None
_DEFAULT_EDGE_COLOR = (0.08, 0.12, 0.16)
_DEFAULT_LINE_COLOR = (0.05, 0.23, 0.55)
_ISOMETRIC_PITCH_DEGREES = 35.26438968
_ISOMETRIC_VIEW_ANGLES: dict[str, tuple[float, float]] = {
    "6": (45.0, _ISOMETRIC_PITCH_DEGREES),
    "7": (-45.0, _ISOMETRIC_PITCH_DEGREES),
    "8": (-135.0, _ISOMETRIC_PITCH_DEGREES),
    "9": (135.0, _ISOMETRIC_PITCH_DEGREES),
}
_LOCAL_AXIS_TURN_KEYS: dict[str, tuple[float, float, float]] = {
    "1": (1.0, 0.0, 0.0),
    "2": (0.0, 1.0, 0.0),
    "3": (0.0, 0.0, 1.0),
}
_LOCAL_AXIS_COLORS: tuple[tuple[float, float, float], ...] = (
    (0.9, 0.05, 0.05),
    (0.05, 0.62, 0.18),
    (0.1, 0.28, 0.95),
)
_LOCAL_AXIS_VIEW_FRACTION = 0.22
_ORTHOGRAPHIC_ZOOM_FACTOR = 0.9
_SCALE_BAR_COLOR = (0.05, 0.06, 0.07)
_SCALE_BAR_MAX_PIXELS = 140.0
_SCALE_BAR_MIN_PIXELS = 36.0
_SCALE_BAR_MARGIN_PIXELS = 24.0
_SCALE_BAR_BOTTOM_PIXELS = 38.0
_SCALE_BAR_TEXT_BOTTOM_PIXELS = 18.0
_SCALE_BAR_TICK_PIXELS = 10.0


@dataclass(frozen=True, slots=True)
class _DrawBatch:
    positions: np.ndarray
    normals: np.ndarray
    colors: np.ndarray
    primitive: str
    index_buffer: object | None = None
    point_size: float = 4.0


@dataclass(frozen=True, slots=True)
class _SceneBounds:
    local_centre: np.ndarray
    radius: float


@dataclass(frozen=True, slots=True)
class _CanvasGeometry:
    face_batches: tuple[_DrawBatch, ...]
    edge_batches: tuple[_DrawBatch, ...]
    point_batches: tuple[_DrawBatch, ...]
    bounds: _SceneBounds


@dataclass(frozen=True, slots=True)
class _ScaleBar:
    exponent: int
    length_units: float
    width_pixels: float
    label: str


def _require_vispy() -> None:
    if not _HAS_VISPY:
        raise ImportError("Interactive 3D viewing requires vispy; install cady[view]")


def _select_vispy_shader_backend(gl: Any) -> None:
    """Keep VisPy's shader conversion aligned with the active GL context."""
    version = gl.glGetParameter(gl.GL_VERSION)
    if isinstance(version, bytes):
        version = version.decode("utf-8", errors="replace")
    if not str(version).startswith("OpenGL ES"):
        return

    backend_name = getattr(gl.current_backend, "__name__", "")
    if ".es" not in backend_name:
        gl.use_gl("es2")


def _translation_matrix(offset: tuple[float, float, float] | np.ndarray) -> np.ndarray:
    matrix = np.eye(4, dtype=np.float32)
    matrix[3, :3] = np.asarray(offset, dtype=np.float32)
    return matrix


def _rotation_matrix(angle_degrees: float, axis: tuple[float, float, float]) -> np.ndarray:
    axis_array = np.asarray(axis, dtype=np.float32)
    length = float(np.linalg.norm(axis_array))
    if length == 0.0:
        raise ValueError("rotation axis must be non-zero")
    x, y, z = axis_array / length
    c = cos(radians(angle_degrees))
    s = np.sin(radians(angle_degrees))
    one_c = 1.0 - c
    return np.array(
        [
            [c + x * x * one_c, y * x * one_c + z * s, z * x * one_c - y * s, 0.0],
            [x * y * one_c - z * s, c + y * y * one_c, z * y * one_c + x * s, 0.0],
            [x * z * one_c + y * s, y * z * one_c - x * s, c + z * z * one_c, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )


def _apply_view_orbit(orientation: np.ndarray, dx_degrees: float, dy_degrees: float) -> np.ndarray:
    yaw = _rotation_matrix(dx_degrees, (0.0, 1.0, 0.0))
    pitch = _rotation_matrix(dy_degrees, (1.0, 0.0, 0.0))
    return (orientation @ yaw @ pitch).astype(np.float32, copy=False)


def _front_orientation() -> np.ndarray:
    return np.eye(4, dtype=np.float32)


def _camera_orientation(camera: Camera) -> np.ndarray:
    position = np.array(camera.position, dtype=np.float32)
    target = np.array(camera.target, dtype=np.float32)
    up_hint = np.array(camera.up, dtype=np.float32)
    z_axis = position - target
    z_axis = z_axis / np.linalg.norm(z_axis)
    x_axis = np.cross(up_hint, z_axis)
    x_axis = x_axis / np.linalg.norm(x_axis)
    y_axis = np.cross(z_axis, x_axis)
    matrix = np.eye(4, dtype=np.float32)
    matrix[:3, 0] = x_axis
    matrix[:3, 1] = y_axis
    matrix[:3, 2] = z_axis
    return matrix


def _isometric_orientation(key: str) -> np.ndarray | None:
    angles = _ISOMETRIC_VIEW_ANGLES.get(key)
    if angles is None:
        return None
    yaw_degrees, pitch_degrees = angles
    return _apply_view_orbit(_front_orientation(), yaw_degrees, pitch_degrees)


def _apply_local_axis_turn(orientation: np.ndarray, axis: tuple[float, float, float]) -> np.ndarray:
    return (_rotation_matrix(90.0, axis) @ orientation).astype(np.float32, copy=False)


def _orientation_for_number_key(orientation: np.ndarray, key: str) -> np.ndarray | None:
    if key == "0":
        return _front_orientation()
    local_axis = _LOCAL_AXIS_TURN_KEYS.get(key)
    if local_axis is not None:
        return _apply_local_axis_turn(orientation, local_axis)
    return _isometric_orientation(key)


def _number_key_name(key: object) -> str | None:
    raw_name = getattr(key, "name", key)
    name = str(raw_name).lower()
    for digit in "0123456789":
        if name in {digit, f"digit{digit}", f"key{digit}", f"num{digit}", f"numpad{digit}"}:
            return digit
    return None


def _axis_toggle_key_pressed(key: object) -> bool:
    raw_name = getattr(key, "name", key)
    return str(raw_name).lower() in {"a", "keya"}


def _model_matrix(local_centre: np.ndarray, orientation: np.ndarray) -> np.ndarray:
    return (_translation_matrix(-local_centre) @ orientation).astype(np.float32, copy=False)


def _projection_clip_planes(radius: float, distance: float, camera: Camera) -> tuple[float, float]:
    near = max(camera.near, radius * 0.001, 0.01)
    far = max(camera.far if camera.far > near else near * 2.0, distance + radius * 4.0)
    return near, far


def _view_relative_axis_length(
    distance: float,
    viewport_size: tuple[int, int],
    *,
    fov_degrees: float,
    view_fraction: float = _LOCAL_AXIS_VIEW_FRACTION,
) -> float:
    width, height = viewport_size
    width_px = max(float(width), 1.0)
    height_px = max(float(height), 1.0)
    target_pixels = min(width_px, height_px) * view_fraction
    visible_world_height = 2.0 * max(float(distance), 1e-6) * tan(radians(fov_degrees) / 2.0)
    return target_pixels * visible_world_height / height_px


def _view_relative_orthographic_axis_length(
    orthographic_scale: float,
    viewport_size: tuple[int, int],
    *,
    view_fraction: float = _LOCAL_AXIS_VIEW_FRACTION,
) -> float:
    width, height = viewport_size
    width_px = max(float(width), 1.0)
    height_px = max(float(height), 1.0)
    target_pixels = min(width_px, height_px) * view_fraction
    return target_pixels * max(float(orthographic_scale), 1e-6) / height_px


def _zoomed_orthographic_scale(
    scale: float,
    wheel_delta: float,
    radius: float,
) -> float:
    minimum = max(radius * 0.001, 1e-6)
    maximum = max(radius * 20.0, minimum * 2.0)
    zoomed = scale * (_ORTHOGRAPHIC_ZOOM_FACTOR**wheel_delta)
    return max(minimum, min(float(zoomed), maximum))


def _scale_bar_label(exponent: int) -> str:
    if exponent == 0:
        return "1 unit"
    return f"1e{exponent} units"


def _scale_bar_for_visible_height(
    visible_world_height: float,
    viewport_size: tuple[int, int],
    *,
    min_pixels: float = _SCALE_BAR_MIN_PIXELS,
    max_pixels: float = _SCALE_BAR_MAX_PIXELS,
) -> _ScaleBar:
    _width, height = viewport_size
    height_px = max(float(height), 1.0)
    units_per_pixel = max(float(visible_world_height), 1e-12) / height_px
    exponent = floor(log10(units_per_pixel * max_pixels))

    while (10.0**exponent) / units_per_pixel < min_pixels:
        exponent += 1

    length_units = 10.0**exponent
    return _ScaleBar(
        exponent=exponent,
        length_units=length_units,
        width_pixels=length_units / units_per_pixel,
        label=_scale_bar_label(exponent),
    )


def _scale_bar_visible_height(
    camera: Camera,
    *,
    distance: float,
    orthographic_scale: float,
) -> float | None:
    if camera.projection == "orthographic":
        return max(float(orthographic_scale), 1e-12)
    return None


def _scale_bar_for_camera(
    camera: Camera,
    *,
    distance: float,
    orthographic_scale: float,
    viewport_size: tuple[int, int],
) -> _ScaleBar | None:
    visible_height = _scale_bar_visible_height(
        camera,
        distance=distance,
        orthographic_scale=orthographic_scale,
    )
    if visible_height is None:
        return None
    return _scale_bar_for_visible_height(visible_height, viewport_size)


def _scale_bar_line_vertices(
    scale_bar: _ScaleBar,
    viewport_size: tuple[int, int],
) -> np.ndarray:
    width, height = viewport_size
    width_px = max(float(width), 1.0)
    height_px = max(float(height), 1.0)
    usable_width = max(width_px - _SCALE_BAR_MARGIN_PIXELS * 2.0, 1.0)
    bar_width = min(scale_bar.width_pixels, usable_width)
    x0 = _SCALE_BAR_MARGIN_PIXELS
    x1 = x0 + bar_width
    y0 = min(_SCALE_BAR_BOTTOM_PIXELS, height_px)
    y1 = min(y0 + _SCALE_BAR_TICK_PIXELS, height_px)
    vertices = np.array(
        [
            (x0, y0),
            (x1, y0),
            (x0, y0),
            (x0, y1),
            (x1, y0),
            (x1, y1),
        ],
        dtype=np.float32,
    )
    clip = np.empty_like(vertices)
    clip[:, 0] = (vertices[:, 0] / width_px) * 2.0 - 1.0
    clip[:, 1] = (vertices[:, 1] / height_px) * 2.0 - 1.0
    return np.ascontiguousarray(clip, dtype=np.float32)


def _local_axis_line_data(
    origin: np.ndarray,
    length: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    basis = np.eye(3, dtype=np.float32) * np.float32(length)
    vertices: list[np.ndarray] = []
    colors: list[tuple[float, float, float]] = []
    for axis_index, rgb in enumerate(_LOCAL_AXIS_COLORS):
        vertices.append(origin.astype(np.float32, copy=True))
        vertices.append((origin + basis[axis_index]).astype(np.float32, copy=False))
        colors.extend((rgb, rgb))
    return (
        np.array(vertices, dtype=np.float32),
        np.array([[0, 1], [2, 3], [4, 5]], dtype=np.uint32),
        np.array(colors, dtype=np.float32),
    )


def _mesh_edge_color(mesh: SceneMesh) -> tuple[float, float, float]:
    if mesh.render_mode == "wireframe":
        return mesh.color
    return _DEFAULT_EDGE_COLOR


def _vertex_attributes(
    positions: np.ndarray,
    normals: np.ndarray,
    colors: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (
        np.ascontiguousarray(positions, dtype=np.float32),
        np.ascontiguousarray(normals, dtype=np.float32),
        np.ascontiguousarray(colors, dtype=np.float32),
    )


def _solid_color_vertices(
    vertices: np.ndarray,
    color: tuple[float, float, float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    colors = np.tile(np.array(color, dtype=np.float32), (len(vertices), 1))
    normals = np.tile(np.array((0.0, 0.0, 1.0), dtype=np.float32), (len(vertices), 1))
    return _vertex_attributes(vertices, normals, colors)


def _line_batch(line: SceneLine, gloo: Any) -> _DrawBatch:
    positions, normals, colors = _solid_color_vertices(line.vertices, line.color)
    return _DrawBatch(
        positions=positions,
        normals=normals,
        colors=colors,
        primitive="lines",
        index_buffer=gloo.IndexBuffer(line.indices),
    )


def _face_batch(mesh: SceneMesh, gloo: Any) -> _DrawBatch | None:
    if mesh.render_mode != "shaded" or len(mesh.faces) == 0:
        return None
    face_vertices, face_indices, face_normals = _shaded_face_buffers(
        mesh.vertices,
        mesh.faces,
    )
    colors = np.tile(np.array(mesh.color, dtype=np.float32), (len(face_vertices), 1))
    positions, normals, color_data = _vertex_attributes(face_vertices, face_normals, colors)
    return _DrawBatch(
        positions=positions,
        normals=normals,
        colors=color_data,
        primitive="triangles",
        index_buffer=gloo.IndexBuffer(face_indices),
    )


def _edge_batch(mesh: SceneMesh, gloo: Any) -> _DrawBatch | None:
    if mesh.render_mode not in {"shaded", "wireframe"}:
        return None
    edge_indices = (
        mesh.edges
        if len(mesh.edges) > 0
        else _orientation_edges(mesh.vertices, mesh.faces)
    )
    if len(edge_indices) == 0:
        return None
    positions, normals, colors = _solid_color_vertices(mesh.vertices, _mesh_edge_color(mesh))
    return _DrawBatch(
        positions=positions,
        normals=normals,
        colors=colors,
        primitive="lines",
        index_buffer=gloo.IndexBuffer(edge_indices),
    )


def _point_batch(mesh: SceneMesh) -> _DrawBatch | None:
    if mesh.render_mode != "points":
        return None
    positions, normals, colors = _solid_color_vertices(mesh.vertices, mesh.color)
    return _DrawBatch(
        positions=positions,
        normals=normals,
        colors=colors,
        primitive="points",
        point_size=mesh.point_size,
    )


def _scene_bounds(geometry_vertices: Sequence[np.ndarray]) -> _SceneBounds:
    if not geometry_vertices:
        raise ValueError("viewer requires at least one vertex")
    all_vertices = np.vstack(geometry_vertices)
    local_centre = (all_vertices.min(axis=0) + all_vertices.max(axis=0)) / 2.0
    spans = all_vertices.max(axis=0) - all_vertices.min(axis=0)
    radius = float(np.max(spans)) * 1.2 or 1.0
    return _SceneBounds(local_centre=local_centre, radius=radius)


def _build_canvas_geometry(prepared: PreparedScene, gloo: Any) -> _CanvasGeometry:
    """Convert prepared scene arrays into GPU-ready draw batches."""
    face_batches: list[_DrawBatch] = []
    edge_batches: list[_DrawBatch] = []
    point_batches: list[_DrawBatch] = []
    geometry_vertices: list[np.ndarray] = []

    for line in prepared.lines:
        geometry_vertices.append(line.vertices)
        edge_batches.append(_line_batch(line, gloo))

    for mesh in prepared.meshes:
        geometry_vertices.append(mesh.vertices)
        face_batch = _face_batch(mesh, gloo)
        if face_batch is not None:
            face_batches.append(face_batch)
        edge_batch = _edge_batch(mesh, gloo)
        if edge_batch is not None:
            edge_batches.append(edge_batch)
        point_batch = _point_batch(mesh)
        if point_batch is not None:
            point_batches.append(point_batch)

    return _CanvasGeometry(
        face_batches=tuple(face_batches),
        edge_batches=tuple(edge_batches),
        point_batches=tuple(point_batches),
        bounds=_scene_bounds(geometry_vertices),
    )


def _make_canvas(
    prepared: PreparedScene,
    *,
    title: str | None = None,
) -> object:
    _require_vispy()

    app = cast(Any, importlib.import_module("vispy.app"))
    gloo = cast(Any, importlib.import_module("vispy.gloo"))
    transforms = cast(Any, importlib.import_module("vispy.util.transforms"))
    visuals = cast(Any, importlib.import_module("vispy.visuals"))
    perspective = transforms.perspective
    ortho = transforms.ortho
    canvas_base = cast(type[Any], app.Canvas)
    geometry = _build_canvas_geometry(prepared, gloo)

    class _Canvas(canvas_base):
        def __init__(self) -> None:
            super().__init__(  # pyright: ignore[reportUnknownMemberType]
                title=title or prepared.name,
                keys="interactive",
                size=(900, 700),
                config={"samples": 4},
            )

            _select_vispy_shader_backend(gloo.gl)
            self._program = gloo.Program(_VERT_SHADER, _FRAG_SHADER)
            self._overlay_program = gloo.Program(_OVERLAY_VERT_SHADER, _OVERLAY_FRAG_SHADER)
            self._camera = prepared.camera
            self._face_batches = geometry.face_batches
            self._edge_batches = geometry.edge_batches
            self._point_batches = geometry.point_batches
            self._local_centre = geometry.bounds.local_centre
            self._radius = geometry.bounds.radius
            requested_distance = float(
                np.linalg.norm(
                    np.array(self._camera.position, dtype=np.float32)
                    - np.array(self._camera.target, dtype=np.float32)
                )
            )
            self._distance = max(requested_distance, self._radius * 0.8)
            self._pan = np.zeros(2, dtype=np.float32)
            self._axis_positions, self._axis_normals, self._axis_colors, self._axis_index_buffer = (
                self._create_axis_buffers(1.0)
            )
            self._scale_bar_positions = _scale_bar_line_vertices(
                _scale_bar_for_visible_height(1.0, self.physical_size),
                self.physical_size,
            )
            self._scale_label = visuals.TextVisual(
                "1 unit",
                color=(*_SCALE_BAR_COLOR, 1.0),
                font_size=11,
                pos=(_SCALE_BAR_MARGIN_PIXELS, 0.0, 0.0),
                anchor_x="left",
                anchor_y="bottom",
                depth_test=False,
            )
            self._show_local_axes = False
            self._orientation = _camera_orientation(self._camera)
            self._orthographic_scale = self._camera.orthographic_scale

            self._last_mouse: tuple[float, float] | None = None
            self._mouse_button: int | None = None

            self._configure_program_uniforms()
            self._configure_canvas_state()

            self._update_matrices()
            self.show()

        def _configure_program_uniforms(self) -> None:
            self._program["u_light_direction"] = prepared.light_direction
            self._program["u_ambient_light"] = prepared.ambient_light
            self._program["u_diffuse_light"] = prepared.diffuse_light
            self._program["u_point_size"] = 4.0

        def _configure_canvas_state(self) -> None:
            gloo.set_state(
                clear_color="white",
                depth_test=True,
                polygon_offset=(1, 1),
                blend_func=("src_alpha", "one_minus_src_alpha"),
                line_width=1.0,
            )

        def _create_axis_buffers(
            self,
            length: float,
        ) -> tuple[np.ndarray, np.ndarray, np.ndarray, object]:
            axis_vertices, axis_indices, axis_colors = _local_axis_line_data(
                self._local_centre,
                length,
            )
            _positions, normals, _colors = _solid_color_vertices(
                axis_vertices,
                (0.0, 0.0, 0.0),
            )
            return (
                np.ascontiguousarray(axis_vertices, dtype=np.float32),
                normals,
                np.ascontiguousarray(axis_colors, dtype=np.float32),
                gloo.IndexBuffer(axis_indices),
            )

        def _update_local_axis_length(self, length: float) -> None:
            self._axis_positions, _, _, _ = self._create_axis_buffers(length)

        def _update_scale_bar(self, viewport_size: tuple[int, int]) -> None:
            width, height = viewport_size
            scale_bar = _scale_bar_for_camera(
                self._camera,
                distance=self._distance,
                orthographic_scale=self._orthographic_scale,
                viewport_size=viewport_size,
            )
            if scale_bar is None:
                return
            self._scale_bar_positions = _scale_bar_line_vertices(scale_bar, viewport_size)
            self._scale_label.text = scale_bar.label

            logical_width, logical_height = cast(tuple[int, int], self.size)
            x_scale = max(float(logical_width), 1.0) / max(float(width), 1.0)
            y_scale = max(float(logical_height), 1.0) / max(float(height), 1.0)
            self._scale_label.pos = (
                _SCALE_BAR_MARGIN_PIXELS * x_scale,
                max(float(logical_height) - _SCALE_BAR_TEXT_BOTTOM_PIXELS * y_scale, 0.0),
                0.0,
            )

        def _projection(self, width: int, height: int) -> np.ndarray:
            near, far = _projection_clip_planes(self._radius, self._distance, self._camera)
            aspect = width / float(max(height, 1))
            if self._camera.projection == "orthographic":
                half_height = self._orthographic_scale / 2.0
                half_width = half_height * aspect
                return cast(
                    np.ndarray,
                    ortho(-half_width, half_width, -half_height, half_height, near, far),
                )
            return cast(
                np.ndarray,
                perspective(self._camera.fov_degrees, aspect, near, far),
            )

        def _update_matrices(self) -> None:
            width, height = cast(tuple[int, int], self.physical_size)
            gloo.set_viewport(0, 0, width, height)

            view = _translation_matrix((self._pan[0], self._pan[1], -self._distance))
            model = _model_matrix(self._local_centre, self._orientation)
            # Keep the local axis triad visually stable on screen as zoom changes.
            if self._camera.projection == "orthographic":
                axis_length = _view_relative_orthographic_axis_length(
                    self._orthographic_scale,
                    (width, height),
                )
            else:
                axis_length = _view_relative_axis_length(
                    self._distance,
                    (width, height),
                    fov_degrees=self._camera.fov_degrees,
                )
            self._update_local_axis_length(axis_length)
            self._update_scale_bar((width, height))

            self._program["u_projection"] = self._projection(width, height)
            self._program["u_view"] = view
            self._program["u_model"] = model

        def _draw_batch(self, batch: _DrawBatch) -> None:
            self._program["a_position"] = batch.positions
            self._program["a_normal"] = batch.normals
            self._program["a_color"] = batch.colors
            if batch.primitive == "points":
                self._program["u_point_size"] = batch.point_size
                self._program.draw(batch.primitive)
                return
            self._program.draw(batch.primitive, batch.index_buffer)

        def _draw_face_batches(self) -> None:
            gloo.set_state(
                blend=False,
                depth_test=True,
                depth_mask=True,
                polygon_offset_fill=True,
            )
            self._program["u_lighting"] = 1.0
            for batch in self._face_batches:
                self._draw_batch(batch)

        def _draw_edge_batches(self) -> None:
            gloo.set_state(
                blend=True,
                depth_test=True,
                depth_mask=False,
                polygon_offset_fill=False,
                line_width=1.0,
            )
            self._program["u_lighting"] = 0.0
            for batch in self._edge_batches:
                self._draw_batch(batch)

        def _draw_point_batches(self) -> None:
            if not self._point_batches:
                return
            gloo.set_state(
                blend=True,
                depth_test=True,
                depth_mask=False,
                polygon_offset_fill=False,
            )
            for batch in self._point_batches:
                self._draw_batch(batch)

        def _draw_local_axes(self) -> None:
            if not self._show_local_axes:
                return
            gloo.set_state(
                blend=False,
                depth_test=False,
                depth_mask=False,
                polygon_offset_fill=False,
                line_width=3.0,
            )
            self._program["a_position"] = self._axis_positions
            self._program["a_normal"] = self._axis_normals
            self._program["a_color"] = self._axis_colors
            self._program.draw("lines", self._axis_index_buffer)

        def _draw_scale_bar(self) -> None:
            if self._camera.projection != "orthographic":
                return
            gloo.set_state(
                blend=True,
                depth_test=False,
                depth_mask=False,
                polygon_offset_fill=False,
                line_width=2.0,
            )
            self._overlay_program["a_position"] = self._scale_bar_positions
            self._overlay_program["u_color"] = _SCALE_BAR_COLOR
            self._overlay_program.draw("lines")
            self._scale_label.transforms.configure(canvas=self)
            self._scale_label.draw()

        def on_draw(self, event: object) -> None:
            gloo.clear(color=True, depth=True)
            self._draw_face_batches()
            self._draw_edge_batches()
            self._draw_point_batches()
            self._draw_local_axes()
            self._draw_scale_bar()
            gloo.set_state(depth_mask=True, line_width=1.0)

        def on_resize(self, event: object) -> None:
            self._update_matrices()

        def on_mouse_press(self, event: Any) -> None:
            self._last_mouse = event.pos
            self._mouse_button = event.button

        def on_mouse_release(self, event: object) -> None:
            self._last_mouse = None
            self._mouse_button = None

        def on_mouse_move(self, event: Any) -> None:
            if self._last_mouse is None:
                return
            x, y = event.pos
            last_x, last_y = self._last_mouse
            dx = x - last_x
            dy = y - last_y

            if self._mouse_button == 1:
                self._orientation = _apply_view_orbit(self._orientation, dx * 0.5, dy * 0.5)
            elif self._mouse_button == 2:
                self._pan[0] += dx * self._radius * 0.003
                self._pan[1] -= dy * self._radius * 0.003

            self._last_mouse = event.pos
            self._update_matrices()
            self.update()

        def on_mouse_wheel(self, event: Any) -> None:
            if self._camera.projection == "orthographic":
                self._orthographic_scale = _zoomed_orthographic_scale(
                    self._orthographic_scale,
                    event.delta[1],
                    self._radius,
                )
            else:
                self._distance -= event.delta[1] * self._radius * 0.1
                self._distance = max(
                    self._radius * 0.5,
                    min(self._distance, self._radius * 20.0),
                )
            self._update_matrices()
            self.update()

        def on_key_press(self, event: Any) -> None:
            if _axis_toggle_key_pressed(event.key):
                self._show_local_axes = not self._show_local_axes
                self.update()
                return
            digit = _number_key_name(event.key)
            if digit is None:
                return
            orientation = _orientation_for_number_key(self._orientation, digit)
            if orientation is None:
                return
            self._orientation = orientation
            self._update_matrices()
            self.update()

    return _Canvas()


def view_scene(scene: Scene, *, tolerance: float = 1e-3, title: str | None = None) -> object:
    """Open an interactive window for a prepared scene."""
    _require_vispy()
    app = cast(Any, importlib.import_module("vispy.app"))
    _make_canvas(prepare_scene(scene, tolerance=tolerance), title=title)
    app.run()
    return None


def view_target(
    target: object,
    *,
    tolerance: float = 1e-3,
    title: str | None = None,
) -> object:
    """Open an interactive window for a single target."""
    scene = Scene.from_target(target, name=title or "cady 3D viewer").with_camera(
        DEFAULT_CAMERA,
        name="camera",
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
    scene = scene.with_camera(DEFAULT_CAMERA, name="camera")
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
    prepared = PreparedScene(
        title,
        (),
        scene_lines,
        DEFAULT_CAMERA,
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
        (0.0, 0.0, -1.0),
    )

    app = cast(Any, importlib.import_module("vispy.app"))
    _make_canvas(prepared, title=title)
    app.run()
    return None


__all__ = [
    "PreparedScene",
    "SceneLine",
    "SceneMesh",
    "prepare_scene",
    "view_lines",
    "view_mesh",
    "view_meshes",
    "view_scene",
    "view_target",
]
