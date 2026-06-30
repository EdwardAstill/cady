"""Interactive 3D scene viewer using VisPy.

VisPy is imported lazily so importing :mod:`cady.view` does not require GUI
packages unless a viewer is actually launched.
"""

from __future__ import annotations

import importlib
import importlib.util
from collections.abc import Sequence
from typing import Any, cast

import numpy as np

from cady.view.draw_batches import DrawBatch as _DrawBatch
from cady.view.draw_batches import build_canvas_geometry as _build_canvas_geometry
from cady.view.draw_batches import mesh_edge_color
from cady.view.interaction import (
    ViewerInteractionState,
    axis_toggle_key_pressed,
    camera_orientation,
    number_key_name,
    projection_clip_planes,
    view_relative_orthographic_axis_length,
    zoomed_orthographic_scale,
)
from cady.view.mesh_buffers import orientation_edges, shaded_face_buffers
from cady.view.overlay_renderers import (
    LocalAxesRenderer,
    create_scale_bar_renderer,
    scale_bar_for_camera,
    scale_bar_for_visible_height,
    scale_bar_overlay,
)
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
_DEFAULT_LINE_COLOR = (0.05, 0.23, 0.55)


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
            self._face_batches = geometry.face_batches
            self._edge_batches = geometry.edge_batches
            self._point_batches = geometry.point_batches
            self._interaction = ViewerInteractionState.from_camera(
                prepared.camera,
                local_centre=geometry.bounds.local_centre,
                radius=geometry.bounds.radius,
            )
            self._local_axes = LocalAxesRenderer.create(
                local_centre=geometry.bounds.local_centre,
                gloo=gloo,
            )
            self._scale_bar = create_scale_bar_renderer(
                prepared,
                overlay_program=self._overlay_program,
                visuals=visuals,
                viewport_size=self.physical_size,
                gloo=gloo,
            )

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

        def _projection(self, width: int, height: int) -> np.ndarray:
            near, far = _projection_clip_planes(
                self._interaction.radius,
                self._interaction.distance,
                self._interaction.camera,
            )
            aspect = width / float(max(height, 1))
            if self._interaction.camera.projection == "orthographic":
                half_height = self._interaction.orthographic_scale / 2.0
                half_width = half_height * aspect
                return cast(
                    np.ndarray,
                    ortho(-half_width, half_width, -half_height, half_height, near, far),
                )
            return cast(
                np.ndarray,
                perspective(self._interaction.camera.fov_degrees, aspect, near, far),
            )

        def _update_matrices(self) -> None:
            width, height = cast(tuple[int, int], self.physical_size)
            gloo.set_viewport(0, 0, width, height)

            self._local_axes.update_length(self._interaction.local_axis_length((width, height)))
            if self._scale_bar is not None:
                self._scale_bar.update(
                    camera=self._interaction.camera,
                    distance=self._interaction.distance,
                    orthographic_scale=self._interaction.orthographic_scale,
                    viewport_size=(width, height),
                    logical_size=cast(tuple[int, int], self.size),
                )

            self._program["u_projection"] = self._projection(width, height)
            self._program["u_view"] = self._interaction.view_matrix()
            self._program["u_model"] = self._interaction.model_matrix()

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
            self._local_axes.draw(self._program)

        def _draw_scale_bar(self) -> None:
            if self._scale_bar is not None:
                self._scale_bar.draw(canvas=self, camera=self._interaction.camera)

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
                self._interaction.orbit(dx, dy)
            elif self._mouse_button == 2:
                self._interaction.pan_by_pixels(dx, dy)

            self._last_mouse = event.pos
            self._update_matrices()
            self.update()

        def on_mouse_wheel(self, event: Any) -> None:
            self._interaction.zoom(event.delta[1])
            self._update_matrices()
            self.update()

        def on_key_press(self, event: Any) -> None:
            if _axis_toggle_key_pressed(event.key):
                self._local_axes.toggle()
                self.update()
                return
            digit = _number_key_name(event.key)
            if digit is None:
                return
            if not self._interaction.set_orientation_for_key(digit):
                return
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
