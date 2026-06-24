"""Interactive 3D scene viewer using VisPy.

VisPy is imported lazily so importing :mod:`cady.visualisation` does not require
GUI packages unless a viewer is actually launched.
"""

from __future__ import annotations

import importlib
import importlib.util
from collections.abc import Sequence
from dataclasses import dataclass
from math import cos, radians, tan
from typing import Any, cast

import numpy as np

from cady.geometry3d import Mesh3D
from cady.numeric.mesh3d import ArrayMesh3
from cady.numeric.transform import Transform3
from cady.product import Assembly, Part
from cady.view import AmbientLight, Camera, DirectionalLight, Scene
from cady.view.style import DisplayStyle
from cady.visualisation.mesh_buffers import orientation_edges as _orientation_edges
from cady.visualisation.mesh_buffers import shaded_face_buffers as _shaded_face_buffers

_VERT_SHADER = """
uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;
attribute vec3 a_position;
attribute vec3 a_normal;
attribute vec3 a_color;
varying vec3 v_color;
varying vec3 v_normal;
void main() {
    v_color = a_color;
    v_normal = normalize((u_model * vec4(a_normal, 0.0)).xyz);
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
    gl_PointSize = 5.0;
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

_HAS_VISPY = importlib.util.find_spec("vispy") is not None
_DEFAULT_MESH_COLOR = (0.45, 0.58, 0.72)
_DEFAULT_EDGE_COLOR = (0.08, 0.12, 0.16)
_DEFAULT_LINE_COLOR = (0.05, 0.23, 0.55)
_DEFAULT_CAMERA = Camera.perspective(
    position=(1.8, -2.0, 1.2),
    target=(0.0, 0.0, 0.0),
    fov_degrees=45.0,
)
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

LineVertices = Sequence[Sequence[float]] | np.ndarray


@dataclass(frozen=True, slots=True)
class SceneMesh:
    name: str
    vertices: np.ndarray
    faces: np.ndarray
    edges: np.ndarray
    color: tuple[float, float, float]
    render_mode: str


@dataclass(frozen=True, slots=True)
class SceneLine:
    name: str
    vertices: np.ndarray
    indices: np.ndarray
    color: tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class PreparedScene:
    name: str
    meshes: tuple[SceneMesh, ...]
    lines: tuple[SceneLine, ...]
    camera: Camera
    ambient_light: tuple[float, float, float]
    diffuse_light: tuple[float, float, float]
    light_direction: tuple[float, float, float]


def _require_vispy() -> None:
    if not _HAS_VISPY:
        raise ImportError("Interactive 3D viewing requires vispy; install cady[visualisation]")


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


def _polyline_indices(vertex_count: int) -> np.ndarray:
    if vertex_count < 2:
        return np.empty((0, 2), dtype=np.uint32)
    starts = np.arange(0, vertex_count - 1, dtype=np.uint32)
    ends = np.arange(1, vertex_count, dtype=np.uint32)
    return np.column_stack((starts, ends)).astype(np.uint32, copy=False)


def _prepare_polyline(vertices: LineVertices) -> tuple[np.ndarray, np.ndarray]:
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


def _make_canvas(
    prepared: PreparedScene,
    *,
    title: str | None = None,
) -> object:
    _require_vispy()

    app = cast(Any, importlib.import_module("vispy.app"))
    gloo = cast(Any, importlib.import_module("vispy.gloo"))
    transforms = cast(Any, importlib.import_module("vispy.util.transforms"))
    perspective = transforms.perspective
    ortho = transforms.ortho
    canvas_base = cast(type[Any], app.Canvas)

    class _Canvas(canvas_base):
        def __init__(self) -> None:
            super().__init__(  # pyright: ignore[reportUnknownMemberType]
                title=title or prepared.name,
                keys="interactive",
                size=(900, 700),
                config={"samples": 4},
            )

            self._program = gloo.Program(_VERT_SHADER, _FRAG_SHADER)
            self._camera = prepared.camera

            self._face_data: list[tuple[np.ndarray, np.ndarray, np.ndarray, object]] = []
            self._edge_data: list[tuple[np.ndarray, np.ndarray, np.ndarray, object]] = []
            self._point_data: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
            geometry_vertices: list[np.ndarray] = []

            for line in prepared.lines:
                geometry_vertices.append(line.vertices)
                colors = np.tile(
                    np.array(line.color, dtype=np.float32),
                    (len(line.vertices), 1),
                )
                normals = np.tile(
                    np.array((0.0, 0.0, 1.0), dtype=np.float32),
                    (len(line.vertices), 1),
                )
                self._edge_data.append(
                    (
                        *_vertex_attributes(line.vertices, normals, colors),
                        gloo.IndexBuffer(line.indices),
                    )
                )

            for mesh in prepared.meshes:
                geometry_vertices.append(mesh.vertices)
                edge_indices = (
                    mesh.edges
                    if len(mesh.edges) > 0
                    else _orientation_edges(mesh.vertices, mesh.faces)
                )
                if mesh.render_mode == "shaded" and len(mesh.faces) > 0:
                    face_vertices, face_indices, face_normals = _shaded_face_buffers(
                        mesh.vertices,
                        mesh.faces,
                    )
                    colors = np.tile(
                        np.array(mesh.color, dtype=np.float32),
                        (len(face_vertices), 1),
                    )
                    positions, normal_data, color_data = _vertex_attributes(
                        face_vertices,
                        face_normals,
                        colors,
                    )
                    self._face_data.append(
                        (positions, normal_data, color_data, gloo.IndexBuffer(face_indices))
                    )

                if mesh.render_mode in {"shaded", "wireframe"} and len(edge_indices) > 0:
                    edge_colors = np.tile(
                        np.array(_DEFAULT_EDGE_COLOR, dtype=np.float32),
                        (len(mesh.vertices), 1),
                    )
                    normals = np.tile(
                        np.array((0.0, 0.0, 1.0), dtype=np.float32),
                        (len(mesh.vertices), 1),
                    )
                    positions, normal_data, color_data = _vertex_attributes(
                        mesh.vertices,
                        normals,
                        edge_colors,
                    )
                    self._edge_data.append(
                        (positions, normal_data, color_data, gloo.IndexBuffer(edge_indices))
                    )

                if mesh.render_mode == "points":
                    colors = np.tile(
                        np.array(mesh.color, dtype=np.float32),
                        (len(mesh.vertices), 1),
                    )
                    normals = np.tile(
                        np.array((0.0, 0.0, 1.0), dtype=np.float32),
                        (len(mesh.vertices), 1),
                    )
                    self._point_data.append(_vertex_attributes(mesh.vertices, normals, colors))

            if not geometry_vertices:
                raise ValueError("viewer requires at least one vertex")
            all_v = np.vstack(geometry_vertices)
            self._local_centre = (all_v.min(axis=0) + all_v.max(axis=0)) / 2.0
            spans = all_v.max(axis=0) - all_v.min(axis=0)
            self._radius = float(np.max(spans)) * 1.2 or 1.0
            requested_distance = float(
                np.linalg.norm(
                    np.array(self._camera.position, dtype=np.float32)
                    - np.array(self._camera.target, dtype=np.float32)
                )
            )
            self._distance = max(requested_distance, self._radius * 0.8)
            self._pan = np.zeros(2, dtype=np.float32)
            axis_vertices, axis_indices, axis_colors = _local_axis_line_data(
                self._local_centre,
                1.0,
            )
            axis_normals = np.tile(
                np.array((0.0, 0.0, 1.0), dtype=np.float32),
                (len(axis_vertices), 1),
            )
            self._axis_positions = np.ascontiguousarray(axis_vertices, dtype=np.float32)
            self._axis_colors = np.ascontiguousarray(axis_colors, dtype=np.float32)
            self._axis_normals = np.ascontiguousarray(axis_normals, dtype=np.float32)
            self._axis_index_buffer = gloo.IndexBuffer(axis_indices)
            self._show_local_axes = False
            self._orientation = _camera_orientation(self._camera)
            self._orthographic_scale = self._camera.orthographic_scale

            self._last_mouse: tuple[float, float] | None = None
            self._mouse_button: int | None = None

            self._program["u_light_direction"] = prepared.light_direction
            self._program["u_ambient_light"] = prepared.ambient_light
            self._program["u_diffuse_light"] = prepared.diffuse_light

            gloo.set_state(
                clear_color="white",
                depth_test=True,
                polygon_offset=(1, 1),
                blend_func=("src_alpha", "one_minus_src_alpha"),
                line_width=1.0,
            )

            self._update_matrices()
            self.show()

        def _update_local_axis_length(self, length: float) -> None:
            axis_vertices, _axis_indices, _axis_colors = _local_axis_line_data(
                self._local_centre,
                length,
            )
            self._axis_positions = np.ascontiguousarray(axis_vertices, dtype=np.float32)

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

            self._program["u_projection"] = self._projection(width, height)
            self._program["u_view"] = view
            self._program["u_model"] = model

        def on_draw(self, event: object) -> None:
            gloo.clear(color=True, depth=True)

            gloo.set_state(
                blend=False,
                depth_test=True,
                depth_mask=True,
                polygon_offset_fill=True,
            )
            self._program["u_lighting"] = 1.0
            for positions, normals, colors, ibuf in self._face_data:
                self._program["a_position"] = positions
                self._program["a_normal"] = normals
                self._program["a_color"] = colors
                self._program.draw("triangles", ibuf)

            gloo.set_state(
                blend=True,
                depth_test=True,
                depth_mask=False,
                polygon_offset_fill=False,
                line_width=1.0,
            )
            self._program["u_lighting"] = 0.0
            for positions, normals, colors, ibuf in self._edge_data:
                self._program["a_position"] = positions
                self._program["a_normal"] = normals
                self._program["a_color"] = colors
                self._program.draw("lines", ibuf)
            if self._point_data:
                gloo.set_state(
                    blend=True,
                    depth_test=True,
                    depth_mask=False,
                    polygon_offset_fill=False,
                )
                for positions, normals, colors in self._point_data:
                    self._program["a_position"] = positions
                    self._program["a_normal"] = normals
                    self._program["a_color"] = colors
                    self._program.draw("points")
            if self._show_local_axes:
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


def prepare_scene(scene: Scene, *, tolerance: float = 1e-3) -> PreparedScene:
    meshes: list[SceneMesh] = []
    lines: list[SceneLine] = []
    for scene_object in scene.objects:
        style = scene_object.style or DisplayStyle()
        if not style.visible:
            continue
        target = scene_object.target
        transform = (
            _transform_from_pose(scene_object.pose) if scene_object.pose is not None else None
        )
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
            meshes.append(
                SceneMesh(
                    scene_object.object_name,
                    np.asarray(mesh.vertices, dtype=np.float32),
                    np.asarray(mesh.faces, dtype=np.uint32),
                    np.asarray(mesh.edges, dtype=np.uint32),
                    _style_color(target, style),
                    style.render_mode,
                )
            )

    if not meshes and not lines:
        raise ValueError("cannot visualise an empty scene")

    camera = _active_camera(scene)
    ambient, diffuse, light_direction = _lighting(scene)
    return PreparedScene(
        scene.name,
        tuple(meshes),
        tuple(lines),
        camera,
        ambient,
        diffuse,
        light_direction,
    )


def view_scene(scene: Scene, *, tolerance: float = 1e-3, title: str | None = None) -> object:
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
    scene = Scene.from_target(target, name=title or "cady 3D viewer").with_camera(
        _DEFAULT_CAMERA,
        name="camera",
    )
    return view_scene(scene, tolerance=tolerance, title=title)


def view_mesh(mesh: object, *, tolerance: float = 1e-3, title: str | None = None) -> object:
    return view_target(mesh, tolerance=tolerance, title=title or "cady 3D mesh")


def view_meshes(
    meshes: Sequence[object],
    *,
    tolerance: float = 1e-3,
    title: str = "cady 3D meshes",
) -> object:
    scene = Scene(name=title)
    for index, mesh in enumerate(meshes):
        scene = scene.add(mesh, name=f"mesh_{index + 1}")
    scene = scene.with_camera(_DEFAULT_CAMERA, name="camera")
    return view_scene(scene, tolerance=tolerance, title=title)


def view_lines(
    lines: Sequence[LineVertices],
    *,
    title: str = "cady 3D wire viewer",
) -> object:
    _require_vispy()
    vertices: list[np.ndarray] = []
    indices: list[np.ndarray] = []
    segment_count = 0
    for line in lines:
        line_vertices, line_indices = _prepare_polyline(line)
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
        _DEFAULT_CAMERA,
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
        (0.0, 0.0, -1.0),
    )

    app = cast(Any, importlib.import_module("vispy.app"))
    _make_canvas(prepared, title=title)
    app.run()
    return None


def _mesh_from_target(target: object, *, tolerance: float) -> ArrayMesh3:
    if isinstance(target, ArrayMesh3):
        return target
    if isinstance(target, Mesh3D):
        return target.to_array(tolerance=tolerance)
    to_mesh = getattr(target, "to_mesh", None)
    if callable(to_mesh):
        mesh = to_mesh(tolerance=tolerance)
        return _mesh_from_target(mesh, tolerance=tolerance)
    to_array = getattr(target, "to_array", None)
    if callable(to_array):
        mesh = to_array(tolerance=tolerance)
        return _mesh_from_target(mesh, tolerance=tolerance)
    raise TypeError(
        "scene target must be Mesh3D, ArrayMesh3, or expose to_mesh(tolerance=...)"
    )


def _line_from_target(
    target: object,
    *,
    transform: Transform3 | None,
) -> tuple[np.ndarray, np.ndarray] | None:
    try:
        vertices, indices = _prepare_polyline(cast(LineVertices, target))
    except (TypeError, ValueError):
        return None
    if transform is not None:
        vertices = transform.apply_points(vertices).astype(np.float32, copy=False)
    return vertices, indices


def _transform_from_pose(pose: object) -> Transform3:
    if isinstance(pose, Transform3):
        return pose
    to_transform3 = getattr(pose, "to_transform3", None)
    if callable(to_transform3):
        transform = to_transform3()
        if isinstance(transform, Transform3):
            return transform
    try:
        values = tuple(float(component) for component in pose)  # type: ignore[reportUnknownVariableType]
    except TypeError:
        values = ()
    if len(values) == 3:
        return Transform3.translation(values[0], values[1], values[2])
    raise TypeError("scene object pose must be Transform3, Pose3-like, or a 3D translation")


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


def _active_camera(scene: Scene) -> Camera:
    if scene.active_camera is not None:
        for name, camera in scene.cameras:
            if name == scene.active_camera:
                return camera
    if scene.cameras:
        return scene.cameras[0][1]
    return _DEFAULT_CAMERA


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
