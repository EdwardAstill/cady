"""Interactive 3D mesh viewer using VisPy.

Lazy-imported — VisPy is loaded only when a viewer function is called.
"""

from __future__ import annotations

import importlib
import importlib.util
from collections.abc import Sequence
from math import cos, radians, tan
from typing import Any, Protocol, cast

import numpy as np

from cady.visualisation.mesh_buffers import orientation_edges as _orientation_edges
from cady.visualisation.mesh_buffers import shaded_face_buffers as _shaded_face_buffers
from cady.visualisation.styles import LINE_COLOR, MESH_COLOR, MESH_EDGE_COLOR

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
_VIEW_FOV_DEGREES = 45.0
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


class _MeshLike(Protocol):
    vertices: Sequence[Sequence[float]]
    faces: Sequence[Sequence[int]]


class _ToArrayLike(Protocol):
    def to_array(self, *, tolerance: float) -> _MeshLike: ...


LineVertices = Sequence[Sequence[float]] | np.ndarray


def _require_vispy() -> None:
    if not _HAS_VISPY:
        raise ImportError("Interactive 3D viewing requires vispy; install cady[visualisation]")


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    return (
        int(hex_color[0:2], 16) / 255.0,
        int(hex_color[2:4], 16) / 255.0,
        int(hex_color[4:6], 16) / 255.0,
    )


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
    matrix = np.array(
        [
            [c + x * x * one_c, y * x * one_c + z * s, z * x * one_c - y * s, 0.0],
            [x * y * one_c - z * s, c + y * y * one_c, z * y * one_c + x * s, 0.0],
            [x * z * one_c + y * s, y * z * one_c - x * s, c + z * z * one_c, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )
    return matrix


def _apply_view_orbit(orientation: np.ndarray, dx_degrees: float, dy_degrees: float) -> np.ndarray:
    """Update local-to-global orientation using screen/view X and Y axes."""
    yaw = _rotation_matrix(dx_degrees, (0.0, 1.0, 0.0))
    pitch = _rotation_matrix(dy_degrees, (1.0, 0.0, 0.0))
    return (orientation @ yaw @ pitch).astype(np.float32, copy=False)


def _front_orientation() -> np.ndarray:
    return np.eye(4, dtype=np.float32)


def _isometric_orientation(key: str) -> np.ndarray | None:
    angles = _ISOMETRIC_VIEW_ANGLES.get(key)
    if angles is None:
        return None
    yaw_degrees, pitch_degrees = angles
    return _apply_view_orbit(_front_orientation(), yaw_degrees, pitch_degrees)


def _apply_local_axis_turn(orientation: np.ndarray, axis: tuple[float, float, float]) -> np.ndarray:
    """Apply a 90 degree turn about one of the object's current local axes."""
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
    """Map local mesh coordinates to centred global/view coordinates."""
    return (_translation_matrix(-local_centre) @ orientation).astype(np.float32, copy=False)


def _projection_clip_planes(radius: float, distance: float) -> tuple[float, float]:
    near = max(radius * 0.001, 0.01)
    far = max(distance + radius * 4.0, 1000.0)
    return near, far


def _view_relative_axis_length(
    distance: float,
    viewport_size: tuple[int, int],
    *,
    fov_degrees: float = _VIEW_FOV_DEGREES,
    view_fraction: float = _LOCAL_AXIS_VIEW_FRACTION,
) -> float:
    """Return a world-space length that renders as a stable fraction of the viewport."""
    width, height = viewport_size
    width_px = max(float(width), 1.0)
    height_px = max(float(height), 1.0)
    target_pixels = min(width_px, height_px) * view_fraction
    visible_world_height = 2.0 * max(float(distance), 1e-6) * tan(radians(fov_degrees) / 2.0)
    return target_pixels * visible_world_height / height_px


def _local_axis_line_data(
    origin: np.ndarray,
    length: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return vertices, indices, and per-vertex RGB colors for local XYZ axes."""
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


def _rgb_from_color(color: str | tuple[float, float, float]) -> tuple[float, float, float]:
    if isinstance(color, str):
        return _hex_to_rgb(color)
    return color


def _polyline_indices(vertex_count: int) -> np.ndarray:
    if vertex_count < 2:
        return np.empty((0, 2), dtype=np.uint32)
    starts = np.arange(0, vertex_count - 1, dtype=np.uint32)
    ends = np.arange(1, vertex_count, dtype=np.uint32)
    return np.column_stack((starts, ends)).astype(np.uint32, copy=False)


def _prepare_polyline(vertices: LineVertices) -> tuple[np.ndarray, np.ndarray]:
    points = np.asarray(vertices, dtype=np.float32)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError("line vertices must be an (N, 3) array")
    return points, _polyline_indices(len(points))


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
    face_vertices: list[np.ndarray],
    face_indices: list[np.ndarray],
    face_normals: list[np.ndarray],
    face_rgb: list[tuple[float, float, float]],
    edge_vertices: list[np.ndarray],
    edge_indices: list[np.ndarray],
    edge_rgb: tuple[float, float, float],
    *,
    title: str,
) -> object:
    _require_vispy()

    app = cast(Any, importlib.import_module("vispy.app"))
    gloo = cast(Any, importlib.import_module("vispy.gloo"))
    transforms = cast(Any, importlib.import_module("vispy.util.transforms"))
    perspective = transforms.perspective
    canvas_base = cast(type[Any], app.Canvas)

    class _Canvas(canvas_base):
        def __init__(self) -> None:
            super().__init__(  # pyright: ignore[reportUnknownMemberType]
                title=title,
                keys="interactive",
                size=(900, 700),
                config={"samples": 4},
            )

            self._program = gloo.Program(_VERT_SHADER, _FRAG_SHADER)

            self._face_data: list[tuple[np.ndarray, np.ndarray, np.ndarray, object]] = []
            for verts, indices, normals, rgb in zip(
                face_vertices, face_indices, face_normals, face_rgb, strict=True
            ):
                if len(indices) == 0:
                    continue
                n = len(verts)
                colors = np.tile(np.array(rgb, dtype=np.float32), (n, 1))
                positions, normal_data, color_data = _vertex_attributes(verts, normals, colors)
                self._face_data.append(
                    (positions, normal_data, color_data, gloo.IndexBuffer(indices))
                )

            self._edge_data: list[tuple[np.ndarray, np.ndarray, np.ndarray, object]] = []
            for verts, indices in zip(edge_vertices, edge_indices, strict=True):
                if len(indices) == 0:
                    continue
                n = len(verts)
                colors = np.tile(np.array(edge_rgb, dtype=np.float32), (n, 1))
                normals = np.tile(np.array((0.0, 0.0, 1.0), dtype=np.float32), (n, 1))
                positions, normal_data, color_data = _vertex_attributes(verts, normals, colors)
                self._edge_data.append(
                    (positions, normal_data, color_data, gloo.IndexBuffer(indices))
                )

            geometry_vertices = [
                verts for verts in [*face_vertices, *edge_vertices] if len(verts) > 0
            ]
            if not geometry_vertices:
                raise ValueError("viewer requires at least one vertex")
            all_v = np.vstack(geometry_vertices)
            self._local_centre = (all_v.min(axis=0) + all_v.max(axis=0)) / 2.0
            spans = all_v.max(axis=0) - all_v.min(axis=0)
            self._radius = float(np.max(spans)) * 1.2 or 1.0
            self._distance = self._radius * 2.5
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

            # ── orbit state ────────────────────────────────────────────────
            self._orientation = _apply_view_orbit(np.eye(4, dtype=np.float32), 25.0, 35.0)

            # ── mouse state ────────────────────────────────────────────────
            self._last_mouse: tuple[float, float] | None = None
            self._mouse_button: int | None = None
            self._dragging = False

            self._program["u_light_direction"] = (0.2, 0.45, 0.9)
            self._program["u_ambient_light"] = (0.38, 0.38, 0.38)
            self._program["u_diffuse_light"] = (0.72, 0.72, 0.72)

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

        def _update_matrices(self) -> None:
            width, height = cast(tuple[int, int], self.physical_size)
            gloo.set_viewport(0, 0, width, height)

            near, far = _projection_clip_planes(self._radius, self._distance)
            projection = perspective(_VIEW_FOV_DEGREES, width / float(height), near, far)
            view = _translation_matrix((self._pan[0], self._pan[1], -self._distance))
            model = _model_matrix(self._local_centre, self._orientation)
            self._update_local_axis_length(
                _view_relative_axis_length(self._distance, (width, height))
            )

            self._program["u_projection"] = projection
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

            if self._mouse_button == 1:  # left → orbit
                self._orientation = _apply_view_orbit(self._orientation, dx * 0.5, dy * 0.5)
            elif self._mouse_button == 2:  # middle → pan
                self._pan[0] += dx * self._radius * 0.003
                self._pan[1] -= dy * self._radius * 0.003

            self._last_mouse = event.pos
            self._update_matrices()
            self.update()

        def on_mouse_wheel(self, event: Any) -> None:
            self._distance -= event.delta[1] * self._radius * 0.1
            self._distance = max(self._radius * 0.5, min(self._distance, self._radius * 20.0))
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


def _prepare_mesh(
    mesh: _MeshLike, face_rgb: tuple[float, float, float], edge_rgb: tuple[float, float, float]
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return (face_vertices, face_indices, face_normals, edge_vertices, edge_indices)."""
    verts = np.array(mesh.vertices, dtype=np.float32)
    faces = np.array(mesh.faces, dtype=np.uint32)
    edges = _orientation_edges(verts, faces)
    render_vertices, render_faces, render_normals = _shaded_face_buffers(verts, faces)
    return render_vertices, render_faces, render_normals, verts, edges


def _mesh_from_object(mesh: object, *, tolerance: float) -> _MeshLike:
    if hasattr(mesh, "to_array") and not hasattr(mesh, "vertices"):
        return cast(_ToArrayLike, mesh).to_array(tolerance=tolerance)
    return cast(_MeshLike, mesh)


def vispy_view_mesh(
    mesh: object,
    *,
    title: str = "cady 3D viewer",
    tolerance: float = 1e-3,
) -> None:
    _require_vispy()
    app = cast(Any, importlib.import_module("vispy.app"))

    mesh_like = _mesh_from_object(mesh, tolerance=tolerance)

    fv, fi, fn, ev, ei = _prepare_mesh(
        mesh_like,
        _hex_to_rgb(MESH_COLOR),
        _hex_to_rgb(MESH_EDGE_COLOR),
    )
    _make_canvas(
        [fv],
        [fi],
        [fn],
        [_hex_to_rgb(MESH_COLOR)],
        [ev],
        [ei],
        _hex_to_rgb(MESH_EDGE_COLOR),
        title=title,
    )
    app.run()


def vispy_view_meshes(
    meshes: list[object],
    *,
    title: str = "cady 3D viewer",
    tolerance: float = 1e-3,
) -> None:
    _require_vispy()
    app = cast(Any, importlib.import_module("vispy.app"))

    face_rgb = _hex_to_rgb(MESH_COLOR)
    edge_rgb = _hex_to_rgb(MESH_EDGE_COLOR)

    fvs: list[np.ndarray] = []
    fis: list[np.ndarray] = []
    fns: list[np.ndarray] = []
    evs: list[np.ndarray] = []
    eis: list[np.ndarray] = []
    for mesh in meshes:
        mesh_like = _mesh_from_object(mesh, tolerance=tolerance)
        fv, fi, fn, ev, ei = _prepare_mesh(mesh_like, face_rgb, edge_rgb)
        fvs.append(fv)
        fis.append(fi)
        fns.append(fn)
        evs.append(ev)
        eis.append(ei)

    _make_canvas(fvs, fis, fns, [face_rgb] * len(fvs), evs, eis, edge_rgb, title=title)
    app.run()


def vispy_view_lines(
    lines: Sequence[LineVertices],
    *,
    title: str = "cady 3D wire viewer",
    color: str | tuple[float, float, float] = LINE_COLOR,
) -> None:
    _require_vispy()
    app = cast(Any, importlib.import_module("vispy.app"))

    vertices: list[np.ndarray] = []
    indices: list[np.ndarray] = []
    segment_count = 0
    for line in lines:
        line_vertices, line_indices = _prepare_polyline(line)
        vertices.append(line_vertices)
        indices.append(line_indices)
        segment_count += len(line_indices)

    if segment_count == 0:
        raise ValueError("vispy_view_lines requires at least one line segment")

    _make_canvas(
        [],
        [],
        [],
        [],
        vertices,
        indices,
        _rgb_from_color(color),
        title=title,
    )
    app.run()
